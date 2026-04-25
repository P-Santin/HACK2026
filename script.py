import random
import csv  
import os
from typing import List, Tuple, Any
from data_collection import cargar_datos_logistica, Layout, visualizar_layout_completo
from Grav import place_shelf_gravity, calculate_fitness

def run_grasp_optimization(layout: Layout, iterations: int = 50) -> Tuple[List[Any], float, List[List[Any]]]:
    best_layout = []
    best_fitness = float('inf')
    best_bays_format = [] 
    
    catalog_shelves = [{'id': k, **v} for k, v in layout.bays.items()]
    
    xs = [p[0] for p in layout.floor_plan]
    ys = [p[1] for p in layout.floor_plan]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    static_polys = [layout.esquinas_obstaculo(obs) for obs in layout.obstacles]
    print(f"Iniciando optimización...")
    
    for i in range(iterations):
        current_total_polys = [] 
        current_shelves_data = [] 
        current_bays_format = [] 
        
        random.shuffle(catalog_shelves)
        bays_to_place = catalog_shelves * 15 
        
        for shelf in bays_to_place:
            start_pos = (random.uniform(min_x, max_x), max_y)
            target_pos = (random.uniform(min_x, max_x), min_y)
            angle = random.choice([0, 90, 180, 270]) 
            
            # Pasamos directamente el floor_plan
            poly, total_poly, final_x, final_y = place_shelf_gravity(
                shelf['id'], layout, angle, 
                start_pos, target_pos, 
                current_total_polys, static_polys, 
                layout.floor_plan
            )
            
            if poly is not None:
                current_total_polys.append(total_poly)
                current_shelves_data.append(shelf)
                current_bays_format.append([shelf['id'], final_x, final_y, angle])
                
        fitness = calculate_fitness(current_shelves_data, layout)
        
        if fitness < best_fitness:
            best_fitness = fitness
            best_layout = current_total_polys
            best_bays_format = current_bays_format
            print(f"Iteración {i+1}: Nuevo mejor fitness -> {best_fitness:.4f}")
            
    return best_layout, best_fitness, best_bays_format

if __name__ == "__main__":
    ruta_datos = "./PublicTestCases/Case0/" 
    try:
        layout_almacen = cargar_datos_logistica(ruta_datos)
        mejor_layout, mejor_score, bays_colocadas = run_grasp_optimization(layout_almacen, iterations=30)
        
        nombre_archivo_salida = "layout_optimizadop0.csv"
        ruta_absoluta = os.path.abspath(nombre_archivo_salida)
        
        with open(ruta_absoluta, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(bays_colocadas)
        
        print(f"\n--- PROCESO FINALIZADO ---")
        print(f"Archivo guardado en: {ruta_absoluta}")
        print(f"Mejor Fitness: {mejor_score:.4f}")
        
        visualizar_layout_completo(
            layout_almacen.floor_plan, 
            layout_almacen.obstacles, 
            layout_almacen.bays, 
            layout_almacen.ceiling, 
            bays_colocadas
        )
    except FileNotFoundError as e:
        print(f"Error: No se han encontrado los archivos en {ruta_datos}")