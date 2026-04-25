import random
import csv  # Nuevo import para manejar la salida de datos
from typing import List, Tuple, Any

from data_collection import cargar_datos_logistica, Layout, visualizar_layout_completo
from Grav import place_shelf_gravity, calculate_fitness

# ==============================================================================
# MOTOR DE OPTIMIZACIÓN (GRASP)
# ==============================================================================

def run_grasp_optimization(layout: Layout, iterations: int = 50) -> Tuple[List[Any], float, List[List[Any]]]:
    """
    Bucle principal de la metaheurística GRASP.
    """
    best_layout = []
    best_fitness = float('inf')
    best_bays_format = [] 
    
    catalog_shelves = [{'id': k, **v} for k, v in layout.bays.items()]
    
    # Extraemos los límites reales (soportando negativos)
    xs = [p[0] for p in layout.floor_plan]
    ys = [p[1] for p in layout.floor_plan]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    area_almacen = 0.0
    n = len(layout.floor_plan)
    for i in range(n):
        j = (i + 1) % n
        area_almacen += layout.floor_plan[i][0] * layout.floor_plan[j][1]
        area_almacen -= layout.floor_plan[j][0] * layout.floor_plan[i][1]
    area_almacen = abs(area_almacen) / 2.0
    
    static_polys = [layout.esquinas_obstaculo(obs) for obs in layout.obstacles]
    
    print(f"Iniciando optimización. Rango X:[{min_x}, {max_x}], Y:[{min_y}, {max_y}]")
    
    for i in range(iterations):
        current_total_polys = [] 
        current_shelves_data = [] 
        current_bays_format = [] 
        
        random.shuffle(catalog_shelves)
        # Intentamos colocar un número alto de estanterías para saturar el área
        bays_to_place = catalog_shelves * 15 
        
        for shelf in bays_to_place:
            # Origen de gravedad aleatorio dentro del rango del almacén
            start_pos = (random.uniform(min_x, max_x), max_y)
            target_pos = (random.uniform(min_x, max_x), min_y)
            angle = random.choice([0, 90, 180, 270]) 
            
            # El motor físico devuelve el polígono y las coordenadas de referencia (final_x, final_y)
            poly, total_poly, final_x, final_y = place_shelf_gravity(
                shelf['id'], layout, angle, 
                start_pos, target_pos, 
                current_total_polys, static_polys, 
                min_x, max_x, min_y, max_y
            )
            
            if poly is not None:
                current_total_polys.append(total_poly)
                current_shelves_data.append(shelf)
                # Guardamos [id, x, y, rotación]
                current_bays_format.append([shelf['id'], final_x, final_y, angle])
                
        fitness = calculate_fitness(current_shelves_data, layout)
        
        if fitness < best_fitness:
            best_fitness = fitness
            best_layout = current_total_polys
            best_bays_format = current_bays_format
            print(f"Iteración {i+1}: Nuevo mejor fitness -> {best_fitness:.4f}")
            
    return best_layout, best_fitness, best_bays_format

# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    # Ruta a los archivos CSV de entrada
    ruta_datos = "./PublicTestCases/Case2/" 
    
    try:
        layout_almacen = cargar_datos_logistica(ruta_datos)
        
        # 1. Ejecutar optimización
        mejor_layout, mejor_score, bays_colocadas = run_grasp_optimization(layout_almacen, iterations=30)
        
        # 2. GENERACIÓN DEL ARCHIVO .CSV
        nombre_archivo_salida = "layout_optimizado_p2.csv"
        with open(nombre_archivo_salida, mode='w', newline='') as file:
            writer = csv.writer(file)
            # Escribimos la cabecera la cabecera es 'id', 'x', 'y', 'rotation'

            # Escribimos los datos de cada estantería
            writer.writerows(bays_colocadas)
        
        print(f"\n--- PROCESO FINALIZADO ---")
        print(f"Archivo generado: {nombre_archivo_salida}")
        print(f"Mejor Fitness: {mejor_score:.4f}")
        print(f"Estanterías colocadas: {len(bays_colocadas)}")
        
        # 3. Visualización gráfica
        visualizar_layout_completo(
            layout_almacen.floor_plan, 
            layout_almacen.obstacles, 
            layout_almacen.bays, 
            layout_almacen.ceiling, 
            bays_colocadas
        )
        
    except FileNotFoundError as e:
        print(f"Error: No se han encontrado los archivos en {ruta_datos}")