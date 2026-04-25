import math
from typing import List, Tuple, Optional, Dict, Any
from data_collection import Layout 
from validator import validate_bay_with_double_gap 

Polygon = List[Tuple[float, float]]

def create_rotated_rect(x: float, y: float, w: float, d: float, angle_deg: float) -> Polygon:
    rad = math.radians(angle_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    puntos_relativos = [(0, 0), (w, 0), (w, d), (0, d)]
    return [(x + px * cos_r - py * sin_r, y + px * sin_r + py * cos_r) for px, py in puntos_relativos]

def place_shelf_gravity(bay_id: int, layout: Layout, angle_deg: float, start_pos: Tuple[float, float], target_pos: Tuple[float, float], placed_total_polys: List[Polygon], static_polys: List[Polygon], floor_plan: Polygon) -> Tuple[Optional[Polygon], Optional[Polygon], Optional[float], Optional[float]]:
    specs = layout.bays[bay_id]
    w, d, h_bay, gap = specs['width'], specs['depth'], specs['height'], specs['gap']
    
    low, high = 0.0, 1.0
    best_poly, best_total_poly, best_x, best_y = None, None, None, None

    for _ in range(10):
        mid = (low + high) / 2.0
        cur_x = start_pos[0] * mid + target_pos[0] * (1 - mid)
        cur_y = start_pos[1] * mid + target_pos[1] * (1 - mid)
        
        test_bay_poly = create_rotated_rect(cur_x, cur_y, w, d, angle_deg)
        
        # Le pasamos el floor_plan completo en vez de los límites cuadrados
        valid_total_poly = validate_bay_with_double_gap(
            test_bay_poly, h_bay, gap, 
            static_polys, placed_total_polys, 
            floor_plan, layout.ceiling
        )

        if valid_total_poly is None: 
            low = mid 
        else: 
            best_poly = test_bay_poly
            best_total_poly = valid_total_poly
            best_x, best_y = cur_x, cur_y
            high = mid 
            
    return best_poly, best_total_poly, best_x, best_y

def calculate_fitness(placed_data: List[Dict[str, Any]], layout: Layout) -> float:
    if not placed_data: return float('inf')
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