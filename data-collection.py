import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

import math

class Layout:
    floor_plan: List[List[float]]
    obstacles: List[Dict[str, Any]]
    ceiling: Dict[str, List[float]]
    bays: Dict[int, Dict[str, Any]]

    def __init__(self, floor_plan, obstacles, ceiling, bays):
        # Atributos principales
        self.floor_plan: List[List[float]] = floor_plan
        self.obstacles: List[Dict[str, Any]] = obstacles
        self.ceiling: Dict[str, List[float]] = ceiling
        self.bays: Dict[int, Dict[str, Any]] = bays

    def esquinas_obstaculo(self, obstaculo: Dict[str, Any]) -> List[tuple]:
        """
        Calcula las 4 esquinas de un obstáculo dado.
        Retorna una lista de tuplas [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        """
        x = obstaculo['x']
        y = obstaculo['y']
        w = obstaculo['width']
        d = obstaculo['depth']
        
        # Calculamos los vértices
        esquina_inf_izq = (x, y)
        esquina_inf_der = (x + w, y)
        esquina_sup_der = (x + w, y + d)
        esquina_sup_izq = (x, y + d)
        
        return [esquina_inf_izq, esquina_inf_der, esquina_sup_der, esquina_sup_izq]
    
  
    def obtener_esquinas_bay(self, bay_data: list) -> List[tuple]:
            """
            bay_data: [id, x, y, rotation]
            """
            bay_id, bx, by, rotation = bay_data
        
            specs = self.bays[bay_id]
            w, d = specs['width'], specs['depth']
            
            rad = math.radians(rotation)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)

            puntos_relativos = [(0, 0), (w, 0), (w, d), (0, d)]
            
            esquinas = []
            for px, py in puntos_relativos:
                # Rotación
                tx = px * cos_r - py * sin_r
                ty = px * sin_r + py * cos_r
                # Traslación a la posición (bx, by)
                esquinas.append((bx + tx, by + ty))
                
            return esquinas
    
    def area_bay(self, bay_data: list) -> int:
        
        specs = self.bays[bay_data[0]]
        w, d = specs['width'], specs['depth']

        return w*d
    
    def calcular_porcentaje_ocupacion(self, lista_bays_colocadas: List[list]) -> float:
        """
        Calcula qué porcentaje del almacén está cubierto por las bahías.
        lista_bays_colocadas: [[id, x, y, rot], ...]
        """
        # 1. Calculamos el área total del almacén (suelo)
        # Usamos la fórmula de Shoelace con self.floor_plan
        n = len(self.floor_plan)
        area_almacen = 0.0
        for i in range(n):
            j = (i + 1) % n
            area_almacen += self.floor_plan[i][0] * self.floor_plan[j][1]
            area_almacen -= self.floor_plan[j][0] * self.floor_plan[i][1]
        area_almacen = abs(area_almacen) / 2.0

        if area_almacen == 0:
            return 0.0

        # 2. Sumamos el área de todas las bahías colocadas
        area_ocupada_total = 0.0
        for bay_data in lista_bays_colocadas:
            # Usamos el ID (bay_data[0]) para calcular el área
            # Asumo que tu método se llama self.get_bay_area(bay_id)
            area_ocupada_total += self.area_bay(bay_data)

        # 3. Calculamos el porcentaje final
        porcentaje = (area_ocupada_total / area_almacen) * 100
        
        return round(porcentaje, 2)
        
        

def cargar_datos_logistica(path_folder: str) -> Layout:
    # Asegurar que el path termina en / si es un string
    if not path_folder.endswith('/') and not path_folder.endswith('\\'):
        path_folder += '/'

    # 1. Warehouse
    df_warehouse = pd.read_csv(f"{path_folder}warehouse.csv", header=None, names=['x', 'y'])
    warehouse_coords = list(df_warehouse.itertuples(index=False, name=None))

    # 2. Obstacles
    df_obstacles = pd.read_csv(f"{path_folder}obstacles.csv", header=None, names=['x', 'y', 'width', 'depth'])
    obstacles = df_obstacles.to_dict(orient='records')

    # 3. Ceiling
    df_ceiling = pd.read_csv(f"{path_folder}ceiling.csv", header=None, names=['x', 'height'])
    ceiling_profile = df_ceiling.to_dict(orient='list')

    # 4. Types of Bays
    df_bays = pd.read_csv(f"{path_folder}types_of_bays.csv", header=None, names=['id', 'width', 'depth', 'height', 'gap', 'n_loads', 'price'])
    bays_catalog = df_bays.set_index('id').to_dict(orient='index')

    # Instanciamos la clase Layout con los datos procesados
    return Layout(
        floor_plan=warehouse_coords,
        obstacles=obstacles,
        ceiling=ceiling_profile,
        bays=bays_catalog
    )
