import pandas as pd
from typing import Any
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
import matplotlib.cm as cm

class Layout:
    floor_plan: list[list[float]]
    obstacles: list[dict[str, Any]]
    ceiling: dict[str, list[float]]
    bays: dict[int, dict[str, Any]]

    def __init__(self, floor_plan, obstacles, ceiling, bays):
        # Atributos principales
        self.floor_plan: list[list[float]] = floor_plan
        self.obstacles: list[dict[str, Any]] = obstacles
        self.ceiling: dict[str, list[float]] = ceiling
        self.bays: dict[int, dict[str, Any]] = bays

    def esquinas_obstaculo(self, obstaculo: dict[str, Any]) -> list[tuple]:
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
    
  
    def obtener_esquinas_bay(self, bay_data: list) -> list[tuple]:
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
    
    def calcular_porcentaje_ocupacion(self, lista_bays_colocadas: list[list]) -> float:
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


def visualizar_layout_completo(floor_plan, obstacles, bays_catalog, ceiling_profile, bays_colocadas):
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # --- 1. PREPARAR EL "CLIP PATH" (MÁSCARA) ---
    # Creamos un polígono con la forma exacta del almacén
    warehouse_poly = patches.Polygon(floor_plan, closed=True, facecolor='none')
    ax.add_patch(warehouse_poly) # Necesitamos añadirlo para usarlo de máscara

    # --- 2. DIBUJAR EL CEILING (LIMITADO AL PLANO) ---
    c_x = ceiling_profile['x']
    c_h = ceiling_profile['height']
    
    y_min, y_max = 0, 10000 
    x_max_fp = max(p[0] for p in floor_plan)
    min_h, max_h = min(c_h), max(c_h)
    
    for i in range(len(c_x)):
        x_start = c_x[i]
        x_end = c_x[i+1] if i+1 < len(c_x) else x_max_fp
        width_seg = x_end - x_start
        
        if width_seg <= 0: continue

        # Cálculo de color (Gris oscuro = Techo bajo)
        if max_h == min_h:
            color_val = 0.2
        else:
            norm_h = (c_h[i] - min_h) / (max_h - min_h)
            color_val = 0.15 + (1.0 - norm_h) * 0.45 
        
        # Dibujamos el rectángulo del techo
        rect_c = patches.Rectangle((x_start, y_min), width_seg, y_max - y_min, 
                                   facecolor=cm.Greys(color_val), alpha=0.5, zorder=0)
        
        # APLICAR MÁSCARA: Aquí está la magia
        rect_c.set_clip_path(warehouse_poly)
        ax.add_patch(rect_c)
        
        # Etiqueta de altura (solo si está dentro o cerca del área)
        ax.text(x_start + 100, 500, f"H: {c_h[i]}", fontsize=8, color='black', alpha=0.5)

    # --- 3. DIBUJAR EL PERÍMETRO (Encima del techo) ---
    fp_x = [p[0] for p in floor_plan] + [floor_plan[0][0]]
    fp_y = [p[1] for p in floor_plan] + [floor_plan[0][1]]
    ax.plot(fp_x, fp_y, color='navy', lw=4, zorder=5)

    # --- 4. DIBUJAR OBSTÁCULOS ---
    for obs in obstacles:
        rect = patches.Rectangle((obs['x'], obs['y']), obs['width'], obs['depth'], 
                                 edgecolor='darkred', facecolor='red', alpha=0.6, zorder=10)
        ax.add_patch(rect)

    # --- 5. DIBUJAR BAHÍAS Y GAPs ---
    for bay in bays_colocadas:
        bay_id, bx, by, rot = bay
        specs = bays_catalog[bay_id]
        w, d, gap = specs['width'], specs['depth'], specs['gap']
        
        rad = math.radians(rot)
        
        # Bahía
        rect_bay = patches.Rectangle((bx, by), w, d, angle=rot,
                                     edgecolor='darkgreen', facecolor='forestgreen', alpha=0.9, zorder=15)
        ax.add_patch(rect_bay)

        # GAP
        off_x = -gap * math.sin(rad)
        off_y = gap * math.cos(rad)
        rect_gap = patches.Rectangle((bx - off_x, by - off_y), w, gap, angle=rot,
                                     edgecolor='orange', facecolor='gold', alpha=0.6, zorder=12)
        ax.add_patch(rect_gap)

        ax.text(bx + 50, by + 50, f"{bay_id}", fontsize=8, color='white', fontweight='bold', zorder=20)

    # Configuración final
    ax.set_aspect('equal')
    ax.set_facecolor('white') # Fondo exterior limpio
    plt.title("Layout Logístico con Techo Recortado a la Planta", pad=20)
    
    # Leyenda
    legend_elements = [
        patches.Patch(color='gray', alpha=0.5, label='Altura Techo (Sombreado Interno)'),
        patches.Patch(color='red', alpha=0.6, label='Obstáculo'),
        patches.Patch(color='forestgreen', label='Bahía'),
        patches.Patch(color='gold', alpha=0.6, label='GAP (Carga)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.show()
