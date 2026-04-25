import math
from typing import List, Tuple, Dict, Optional

Polygon = List[Tuple[float, float]]
CeilingProfile = Dict[str, List[float]]

def get_ceiling_height(x: float, ceiling_profile: CeilingProfile) -> float:
    xs = ceiling_profile['x']
    hs = ceiling_profile['height']
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i+1]:
            return hs[i]
    return hs[-1] if hs else float('inf')

def is_ceiling_valid(poly_points: Polygon, bay_h: float, ceiling_profile: CeilingProfile) -> bool:
    xs = [p[0] for p in poly_points]
    min_x, max_x = min(xs), max(xs)
    if bay_h > get_ceiling_height(min_x, ceiling_profile): return False
    if bay_h > get_ceiling_height(max_x, ceiling_profile): return False
    for cx, ch in zip(ceiling_profile['x'], ceiling_profile['height']):
        if min_x < cx < max_x and bay_h > ch: return False
    return True

def polygons_overlap(poly1: Polygon, poly2: Polygon) -> bool:
    def get_axes(p: Polygon) -> List[Tuple[float, float]]:
        axes = []
        for i in range(len(p)):
            p1, p2 = p[i], p[(i + 1) % len(p)]
            edge = (p2[0] - p1[0], p2[1] - p1[1])
            normal = (-edge[1], edge[0])
            length = math.hypot(*normal)
            if length > 0: axes.append((normal[0]/length, normal[1]/length))
        return axes

    def project(p: Polygon, axis: Tuple[float, float]) -> Tuple[float, float]:
        projs = [(pt[0] * axis[0] + pt[1] * axis[1]) for pt in p]
        return min(projs), max(projs)

    for axis in get_axes(poly1) + get_axes(poly2):
        min1, max1 = project(poly1, axis)
        min2, max2 = project(poly2, axis)
        if max1 < min2 or max2 < min1: return False
    return True

def is_point_in_polygon(point: Tuple[float, float], polygon: Polygon) -> bool:
    """Ray-Casting: Comprueba si un punto está dentro de los muros reales (forma de L, etc)"""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
    return inside

def calculate_total_poly(p: Polygon, gap: float) -> Polygon:
    """Genera el rectángulo físico + gap SIEMPRE en la misma posición para cuadrar con Matplotlib"""
    p1, p2, p3, p4 = p[0], p[1], p[2], p[3]
    v_y = (p4[0] - p1[0], p4[1] - p1[1])
    length = math.hypot(*v_y)
    if length == 0: return p
    gx = (v_y[0] / length) * gap
    gy = (v_y[1] / length) * gap
    return [(p1[0]-gx, p1[1]-gy), (p2[0]-gx, p2[1]-gy), p3, p4]

def check_full_collision(total_poly: Polygon, static_polys: List[Polygon], placed_total_polys: List[Polygon], floor_plan: Polygon) -> bool:
    """Valida límites exactos de los muros y colisiones físicas"""
    for px, py in total_poly:
        if not is_point_in_polygon((px, py), floor_plan): return False
    for obs in static_polys:
        if polygons_overlap(total_poly, obs): return False
    for other in placed_total_polys:
        if polygons_overlap(total_poly, other): return False
    return True

def validate_bay_with_double_gap(bay_phys_points: Polygon, bay_h: float, gap_size: float, static_polys: List[Polygon], placed_total_polys: List[Polygon], floor_plan: Polygon, ceiling_profile: CeilingProfile) -> Optional[Polygon]:
    if not is_ceiling_valid(bay_phys_points, bay_h, ceiling_profile): return None
    # ELIMINADO EL BUCLE. Ahora físicas y gráfica hablan el mismo idioma.
    poly_total = calculate_total_poly(bay_phys_points, gap_size)
    if not is_ceiling_valid(poly_total, bay_h, ceiling_profile):
        return None
    if check_full_collision(poly_total, static_polys, placed_total_polys, floor_plan):
        return poly_total 
    return None