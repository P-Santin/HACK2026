import math
import random

# Variables globales de estado
placed_shelves = [] # Lista de polígonos
loading_zones = []  # Polígonos con los que SÍ se puede solapar (no se usan en validación de choques)
    
def get_edges_normals(polygon):
    """Calcula los vectores perpendiculares (ejes) de cada borde del polígono."""
    normals = []
    for i in range(len(polygon)):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % len(polygon)]
        
        # Vector del borde
        edge = (p2[0] - p1[0], p2[1] - p1[1])
        # Vector normal (perpendicular)
        normal = (-edge[1], edge[0])
        
        # Normalizar el vector (opcional pero recomendado para precisión)
        length = math.hypot(normal[0], normal[1])
        if length > 0:
            normals.append((normal[0] / length, normal[1] / length))
    return normals

def project_polygon(axis, polygon):
    """Proyecta todos los vértices del polígono sobre el eje dado y devuelve [min, max]."""
    # Producto escalar del primer punto para inicializar
    min_proj = max_proj = (polygon[0][0] * axis[0]) + (polygon[0][1] * axis[1])
    
    for p in polygon[1:]:
        proj = (p[0] * axis[0]) + (p[1] * axis[1])
        if proj < min_proj:
            min_proj = proj
        elif proj > max_proj:
            max_proj = proj
            
    return min_proj, max_proj

def is_colliding_sat(poly1, poly2):
    """
    Teorema de Ejes Separados. 
    Si encontramos UN SOLO EJE donde las proyecciones no se solapen, NO HAY COLISIÓN.
    """
    axes = get_edges_normals(poly1) + get_edges_normals(poly2)
    
    for axis in axes:
        min1, max1 = project_polygon(axis, poly1)
        min2, max2 = project_polygon(axis, poly2)
        
        # Si hay un hueco entre las proyecciones, tenemos un Eje Separador
        if max1 < min2 or max2 < min1:
            return False # ¡No chocan!
            
    return True # Chocan en todos los ejes

def get_aabb(polygon):
    """Devuelve la caja delimitadora (min_x, max_x, min_y, max_y)"""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), max(xs), min(ys), max(ys)

def aabb_intersect(box1, box2):
    """Comprueba si dos cajas delimitadoras se tocan (rapidísimo)"""
    return not (box1[1] < box2[0] or box1[0] > box2[1] or 
                box1[3] < box2[2] or box1[2] > box2[3])

def is_inside_warehouse(test_aabb, warehouse_width, warehouse_height):
    """Comprueba si la caja delimitadora de la estantería está 100% dentro del almacén."""
    min_x, max_x, min_y, max_y = test_aabb
    return (min_x >= 0 and max_x <= warehouse_width and 
            min_y >= 0 and max_y <= warehouse_height)

def place_shelf_gravity(w, h, angle_deg, start_pos, target_pos, placed_shelves, placed_aabbs):
    """
    Lanza una estantería desde start_pos hacia target_pos.
    Devuelve el polígono en la posición final válida más cercana al target.
    """
    low = 0.0  # El target (0% de distancia al objetivo)
    high = 1.0 # El inicio (100% de distancia al objetivo)
    
    best_poly = None
    best_aabb = None
    
    # 10 iteraciones logarítmicas dan precisión sub-milimétrica
    for _ in range(10):
        mid = (low + high) / 2.0
        
        # Interpolación lineal de la posición
        cur_x = start_pos[0] * mid + target_pos[0] * (1 - mid)
        cur_y = start_pos[1] * mid + target_pos[1] * (1 - mid)
        
        test_poly = create_rotated_rect(cur_x, cur_y, w, h, angle_deg)
        test_aabb = get_aabb(test_poly)
        
        collision = False
        
        # Comprobar contra el almacén (debes definir warehouse_poly previamente)
        if not is_inside_warehouse(test_poly): collision = True
        
        # Comprobar contra las estanterías colocadas
        if not collision:
            for i in range(len(placed_shelves)):
                # 1. Filtro rápido
                if aabb_intersect(test_aabb, placed_aabbs[i]):
                    # 2. Filtro preciso (TU CÓDIGO)
                    if is_colliding_sat(test_poly, placed_shelves[i]):
                        collision = True
                        break
                        
        if collision:
            # Choca. Hay que retroceder (acercarnos a start_pos)
            low = mid
        else:
            # Válido. Lo guardamos e intentamos empujar más hacia el target
            best_poly = test_poly
            best_aabb = test_aabb
            high = mid
            
    return best_poly, best_aabb

def calculate_fitness(placed_shelves_data, warehouse_area):
    """Calcula: ((sum prices)/(sum loads))^(2 - PercentageAreaUsed)"""
    if not placed_shelves_data: return float('inf')
    
    total_price = sum(shelf['price'] for shelf in placed_shelves_data)
    total_load = sum(shelf['load'] for shelf in placed_shelves_data)
    
    # Área usada (ancho * alto de cada estantería colocada)
    used_area = sum(shelf['w'] * shelf['h'] for shelf in placed_shelves_data)
    percentage_area_used = used_area / warehouse_area
    
    if total_load == 0: return float('inf')
    
    base = total_price / total_load
    exponent = 2.0 - percentage_area_used
    
    return base ** exponent

def run_grasp_optimization(catalog_shelves, warehouse_width, warehouse_height, iterations=50):
    best_layout = []
    best_fitness = float('inf')
    
    for _ in range(iterations):
        current_shelves_polys = []
        current_shelves_aabbs = []
        current_shelves_data = [] # Guarda info de precio/carga
        
        # Mezclamos el catálogo para darle aleatoriedad (Fase Greedy-Random)
        random.shuffle(catalog_shelves)
        
        for shelf in catalog_shelves:
            # 1. Definir vector de gravedad aleatorio (desde los bordes hacia adentro)
            start_pos = (random.uniform(0, warehouse_width), warehouse_height)
            target_pos = (random.uniform(0, warehouse_width), 0)
            angle = random.choice([0, 90, 180, 270]) # Ángulos discretos para la base
            
            # 2. Dejar caer
            poly, aabb = place_shelf_gravity(
                shelf['w'], shelf['h'], angle, 
                start_pos, target_pos, 
                current_shelves_polys, current_shelves_aabbs
            )
            
            # 3. Si se pudo colocar, lo guardamos en el layout actual
            if poly is not None:
                current_shelves_polys.append(poly)
                current_shelves_aabbs.append(aabb)
                current_shelves_data.append(shelf)
                
        # 4. Evaluar layout completo
        fitness = calculate_fitness(current_shelves_data, warehouse_width * warehouse_height)
        
        # Como queremos MINIMIZAR la función:
        if fitness < best_fitness:
            best_fitness = fitness
            best_layout = current_shelves_polys
            
    return best_layout, best_fitness