import random
from typing import List, Tuple, Any
from yogi import read

from data_collection import cargar_datos_logistica, Layout, visualizar_layout_completo
from Grav import place_shelf_gravity, calculate_fitness

def run_grasp_optimization(layout: Layout, iterations: int = 50) -> Tuple[List[List[Tuple[float, float]]], float, List[List[Any]]]:
    """
    Bucle principal de la metaheurística GRASP.
    
    Args:
        layout (Layout): Objeto con datos de obstáculos, techo y almacén.
        iterations (int): Número de layouts completos a generar antes de elegir el mejor.
        
    Returns:
        Tuple: (Mejor layout de polígonos, Mejor Fitness, Lista formateada para el visualizador)
    """
    best_layout = []
    best_fitness = float('inf')
    best_bays_format = [] 
    
    catalog_shelves = [{'id': k, **v} for k, v in layout.bays.items()]
    
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
    
    print(f"Iniciando optimización. Dimensiones: X[{min_x}, {max_x}], Y[{min_y}, {max_y}], Área: {area_almacen}")
    
    for i in range(iterations):
        current_total_polys = [] 
        current_shelves_data = [] 
        current_bays_format = [] 
        
        random.shuffle(catalog_shelves)
        bays_to_place = catalog_shelves * 10 
        
        for shelf in bays_to_place:
            start_pos = (random.uniform(min_x, max_x), max_y)
            target_pos = (random.uniform(min_x, max_x), min_y)
            angle = random.choice([0, 90, 180, 270]) 
            
            poly, total_poly, final_x, final_y = place_shelf_gravity(
                shelf['id'], layout, angle, 
                start_pos, target_pos, 
                current_total_polys, static_polys, 
                min_x, max_x, min_y, max_y
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
            print(f"Iteración {i+1}: Nuevo mejor fitness encontrado -> {best_fitness:.4f}")
            
    return best_layout, best_fitness, best_bays_format

if __name__ == "__main__":
    
    case_dir = read(str)
    ruta_datos = "./PublicTestCases/" + case_dir + "/" 
    
    try:
        layout_almacen = cargar_datos_logistica(ruta_datos)
        
        mejor_layout, mejor_score, bays_colocadas = run_grasp_optimization(layout_almacen, iterations=20)
        
        print("\n--- RESULTADO FINAL ---")
        print(f"Mejor Fitness (Mínimo coste ponderado): {mejor_score:.4f}")
        print(f"Total de estanterías colocadas: {len(bays_colocadas)}")
        
        visualizar_layout_completo(
            layout_almacen.floor_plan, 
            layout_almacen.obstacles, 
            layout_almacen.bays, 
            layout_almacen.ceiling, 
            bays_colocadas
        )
        
    except FileNotFoundError as e:
        print(f"Error cargando CSVs: {e}")