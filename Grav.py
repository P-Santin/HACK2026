import math
from typing import List, Tuple, Optional, Dict, Any
from data_collection import Layout 
from validator import calculate_polygons, is_ceiling_valid, check_full_collision

Polygon = List[Tuple[float, float]]

def place_shelf_gravity(bay_id: int, layout: Layout, angle_deg: float, start_pos: Tuple[float, float], target_pos: Tuple[float, float], placed_bays: List[Dict[str, Polygon]], static_polys: List[Polygon], floor_plan: Polygon) -> Tuple[Optional[Polygon], Optional[Polygon], Optional[float], Optional[float]]:
    specs = layout.bays[bay_id]
    w, d, h_bay, gap = specs['width'], specs['depth'], specs['height'], specs['gap']
    
    # Linear step search (Raycast-like) instead of buggy binary search
    steps = 50 
    dx = (target_pos[0] - start_pos[0]) / steps
    dy = (target_pos[1] - start_pos[1]) / steps

    best_bay, best_gap, best_x, best_y = None, None, None, None
    was_valid = False

    for i in range(steps + 1):
        cur_x = start_pos[0] + dx * i
        cur_y = start_pos[1] + dy * i
        
        bay_poly, gap_poly = calculate_polygons(cur_x, cur_y, w, d, gap, angle_deg)
        
        is_valid = False
        if is_ceiling_valid(bay_poly, h_bay, layout.ceiling) and is_ceiling_valid(gap_poly, h_bay, layout.ceiling):
            if check_full_collision(bay_poly, gap_poly, static_polys, placed_bays, floor_plan):
                is_valid = True

        if is_valid:
            best_bay, best_gap = bay_poly, gap_poly
            best_x, best_y = cur_x, cur_y
            was_valid = True
        else:
            if was_valid:
                # The bay was sliding fine but hit an obstacle or the wall. Stop gravity here.
                break 
            
    return best_bay, best_gap, best_x, best_y

def calculate_fitness(placed_data: List[Dict[str, Any]], layout: Layout) -> float:
    # Function entirely untouched as requested
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
    return max(total_price / total_load,1) ** (2.0 - percentage_area_used) if total_load > 0 else float('inf')