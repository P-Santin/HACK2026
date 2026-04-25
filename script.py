import random

from data_collection import cargar_datos_logistica, Layout, visualizar_layout_completo
from Grav import place_shelf_gravity, calculate_fitness

# ==============================================================================
# MOTOR DE OPTIMIZACIÓN (GRASP)
# ==============================================================================

def run_grasp_optimization(layout: Layout, iterations=50):
    best_layout = []
    best_fitness = float('inf')
    best_bays_format = [] # Guardará el formato para el visualizador
    
    # Extraer catálogo como lista de diccionarios
    catalog_shelves = [{'id': k, **v} for k, v in layout.bays.items()]
    
    # Calcular dimensiones máximas del almacén a partir de floor_plan
    xs = [p[0] for p in layout.floor_plan]
    ys = [p[1] for p in layout.floor_plan]
    max_w, max_h = max(xs), max(ys)
    
    # Área total para el fitness (fórmula de Gauss / Shoelace)
    area_almacen = 0.0
    n = len(layout.floor_plan)
    for i in range(n):
        j = (i + 1) % n
        area_almacen += layout.floor_plan[i][0] * layout.floor_plan[j][1]
        area_almacen -= layout.floor_plan[j][0] * layout.floor_plan[i][1]
    area_almacen = abs(area_almacen) / 2.0
    
    # PREPARAR OBSTÁCULOS ESTÁTICOS
    static_polys = []
    for obs in layout.obstacles:
        poly = layout.esquinas_obstaculo(obs)
        static_polys.append(poly)
    
    print(f"Iniciando optimización. Dimensiones: {max_w}x{max_h}, Área: {area_almacen}")
    
    for i in range(iterations):
        current_total_polys = [] # Importante: Aquí guardamos Bahía+Gap para no pisarlos
        current_shelves_data = [] 
        current_bays_format = [] 
        
        # Mezclamos el catálogo
        random.shuffle(catalog_shelves)
        
        # Repetimos el catálogo unas cuantas veces para intentar llenar el almacén
        bays_to_place = catalog_shelves * 10 
        
        for shelf in bays_to_place:
            # Vector de gravedad (esquina superior izq cayendo hacia el centro inferior)
            start_pos = (random.uniform(0, max_w), max_h)
            target_pos = (random.uniform(0, max_w), 0)
            angle = random.choice([0, 90, 180, 270]) 
            
            # LLAMADA ACTUALIZADA (Nuevos argumentos y variables de retorno)
            poly, total_poly, final_x, final_y = place_shelf_gravity(
                shelf['id'], layout, angle, 
                start_pos, target_pos, 
                current_total_polys, static_polys, max_w, max_h
            )
            
            if poly is not None:
                # Guardamos el polígono extendido para que las siguientes no lo pisen
                current_total_polys.append(total_poly)
                current_shelves_data.append(shelf)
                # Formato exacto que pide matplotlib
                current_bays_format.append([shelf['id'], final_x, final_y, angle])
                
        # Fitness desde Grav.py
        fitness = calculate_fitness(current_shelves_data, layout)
        
        if fitness < best_fitness:
            best_fitness = fitness
            best_layout = current_total_polys
            best_bays_format = current_bays_format
            print(f"Iteración {i+1}: Nuevo mejor fitness encontrado -> {best_fitness:.4f}")
            
    return best_layout, best_fitness, best_bays_format

# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    # Asegúrate de poner la ruta correcta a la carpeta donde están tus CSVs
    ruta_datos = "./PublicTestCases/" 
    
    try:
        layout_almacen = cargar_datos_logistica(ruta_datos)
        
        # Ejecutar el algoritmo
        mejor_layout, mejor_score, bays_colocadas = run_grasp_optimization(layout_almacen, iterations=20)
        
        print("\n--- RESULTADO FINAL ---")
        print(f"Mejor Fitness (Mínimo coste ponderado): {mejor_score:.4f}")
        print(f"Total de estanterías colocadas: {len(bays_colocadas)}")
        
        # LLAMADA AL VISUALIZADOR
        visualizar_layout_completo(
            layout_almacen.floor_plan, 
            layout_almacen.obstacles, 
            layout_almacen.bays, 
            layout_almacen.ceiling, 
            bays_colocadas
        )
        
    except FileNotFoundError as e:
        print(f"Error cargando CSVs: {e}")
        print("Comprueba que 'ruta_datos' apunta a la carpeta correcta.")