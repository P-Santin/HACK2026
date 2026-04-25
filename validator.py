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

def segments_intersect(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    """Checks if line segment p1-p2 intersects with line segment p3-p4."""
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

def polygon_edges_intersect(poly1: Polygon, poly2: Polygon) -> bool:
    """Checks if any edge of poly1 crosses any edge of poly2."""
    for i in range(len(poly1)):
        a1, a2 = poly1[i], poly1[(i + 1) % len(poly1)]
        for j in range(len(poly2)):
            b1, b2 = poly2[j], poly2[(j + 1) % len(poly2)]
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False

def is_poly_inside_floor_plan(poly: Polygon, floor_plan: Polygon) -> bool:
    """Validates that a polygon is entirely inside the room, with no walls crossing through it."""
    for p in poly:
        if not is_point_in_polygon(p, floor_plan): return False
    if polygon_edges_intersect(poly, floor_plan): return False
    return True

def calculate_polygons(x: float, y: float, w: float, d: float, gap: float, angle_deg: float) -> Tuple[Polygon, Polygon]:
    """Generates precise Bay and Gap polygons anchoring at (x,y), matching Matplotlib logic exactly."""
    rad = math.radians(angle_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)

    def transform(px, py):
        tx = px * cos_r - py * sin_r
        ty = px * sin_r + py * cos_r
        return (x + tx, y + ty)

    # Bay relative vertices
    bay_pts = [(0, 0), (w, 0), (w, d), (0, d)]
    bay_poly = [transform(px, py) for px, py in bay_pts]

    # Gap relative vertices (attached to bottom edge y=0)
    gap_pts = [(0, -gap), (w, -gap), (w, 0), (0, 0)]
    gap_poly = [transform(px, py) for px, py in gap_pts]

    return bay_poly, gap_poly

def check_full_collision(bay_poly: Polygon, gap_poly: Polygon, static_polys: List[Polygon], placed_bays: List[Dict[str, Polygon]], floor_plan: Polygon) -> bool:
    """Validates limits and selectively checks collisions (allowing gap-gap overlaps)."""
    # 1. Must be inside warehouse
    if not is_poly_inside_floor_plan(bay_poly, floor_plan): return False
    if not is_poly_inside_floor_plan(gap_poly, floor_plan): return False

    # 2. Neither can hit static obstacles
    for obs in static_polys:
        if polygons_overlap(bay_poly, obs): return False
        if polygons_overlap(gap_poly, obs): return False

    # 3. Check against already placed bays
    for placed in placed_bays:
        p_bay = placed['bay']
        p_gap = placed['gap']

        if polygons_overlap(bay_poly, p_bay): return False  # Bay hits Bay
        if polygons_overlap(bay_poly, p_gap): return False  # Bay hits Gap
        if polygons_overlap(gap_poly, p_bay): return False  # Gap hits Bay
        # NOTE: polygons_overlap(gap_poly, p_gap) is intentionally OMITTED here! Overlap is allowed.

    return True