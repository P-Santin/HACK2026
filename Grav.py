import math
import random
# Importamos lo necesario de tu otro script
from data_collection import Layout 
# Asumimos que el validador externo está en 'validator.py'
from validator import validate_bay_with_double_gap 

def create_rotated_rect(x, y, w, d, angle_deg):
    """Genera los vértices basándose en la lógica de obtener_esquinas_bay."""
    rad = math.radians(angle_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    puntos_relativos = [(0, 0), (w, 0), (w, d), (0, d)]
    return [(x + px * cos_r - py * sin_r, y + px * sin_r + py * cos_r) for px, py in puntos_relativos]

def get_edges_normals(polygon):
    normals = []
    for i in range(len(polygon)):
        p1, p2 = polygon[i], polygon[(i + 1) % len(polygon)]
        edge = (p2[0] - p1[0], p2[1] - p1[1])
        normal = (-edge[1], edge[0])
        length = math.hypot(*normal)
        if length > 0: normals.append((normal[0]/length, normal[1]/length))
    return normals

def project_polygon(axis, polygon):
    projs = [(p[0] * axis[0] + p[1] * axis[1]) for p in polygon]
    return min(projs), max(projs)

def is_colliding_sat(poly1, poly2):
    for axis in get_edges_normals(poly1) + get_edges_normals(poly2):
        min1, max1 = project_polygon(axis, poly1)
        min2, max2 = project_polygon(axis, poly2)
        if max1 < min2 or max2 < min1: return False
    return True

def get_aabb(polygon):
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    return min(xs), max(xs), min(ys), max(ys)

def aabb_intersect(box1, box2):
    return not (box1[1] < box2[0] or box1[0] > box2[1] or box1[3] < box2[2] or box1[2] > box2[3])

def is_inside_warehouse(test_aabb, max_w, max_h):
    min_x, max_x, min_y, max_y = test_aabb
    return min_x >= 0 and max_x <= max_w and min_y >= 0 and max_y <= max_h

def place_shelf_gravity(bay_id, layout, angle_deg, start_pos, target_pos, placed_total_polys, static_polys, max_w, max_h):
    specs = layout.bays[bay_id]
    w, d, h_bay, gap = specs['width'], specs['depth'], specs['height'], specs['gap']
    
    low, high = 0.0, 1.0
    best_poly = None
    best_total_poly = None
    best_x, best_y = None, None

    for _ in range(10):
        mid = (low + high) / 2.0
        cur_x = start_pos[0] * mid + target_pos[0] * (1 - mid)
        cur_y = start_pos[1] * mid + target_pos[1] * (1 - mid)
        
        test_bay_poly = create_rotated_rect(cur_x, cur_y, w, d, angle_deg)
        
        # LLAMADA AL NUEVO VALIDADOR
        valid_total_poly = validate_bay_with_double_gap(
            test_bay_poly, h_bay, gap, 
            static_polys, placed_total_polys, 
            max_w, max_h, layout.ceiling
        )

        if valid_total_poly is None: 
            low = mid # Hay colisión o techo bajo
        else: 
            best_poly = test_bay_poly
            best_total_poly = valid_total_poly
            best_x, best_y = cur_x, cur_y
            high = mid # Es válido, empujamos más
            
    return best_poly, best_total_poly, best_x, best_y


def calculate_fitness(placed_data, layout):
    if not placed_data: return float('inf')
    
    # Shoelace para el área del almacén
    area_almacen = 0.0
    for i in range(len(layout.floor_plan)):
        p1, p2 = layout.floor_plan[i], layout.floor_plan[(i + 1) % len(layout.floor_plan)]
        area_almacen += (p1[0] * p2[1] - p2[0] * p1[1])
    area_almacen = abs(area_almacen) / 2.0

    total_price = sum(d['price'] for d in placed_data)
    total_load = sum(d['n_loads'] for d in placed_data)
    used_area = sum(d['width'] * d['depth'] for d in placed_data)
    
    percentage_area_used = used_area / area_almacen if area_almacen > 0 else 0
    return (total_price / total_load) ** (2.0 - percentage_area_used) if total_load > 0 else float('inf')