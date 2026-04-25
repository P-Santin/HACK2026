import math
from typing import List, Tuple, Dict, Optional

Polygon = List[Tuple[float, float]]
CeilingProfile = Dict[str, List[float]]


# ---------------------------------------------------------------------------
# CEILING CHECKS
# ---------------------------------------------------------------------------

def get_ceiling_height(x: float, ceiling_profile: CeilingProfile) -> float:
    """Returns the ceiling height at a given x coordinate."""
    xs = ceiling_profile['x']
    hs = ceiling_profile['height']
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            return hs[i]
    return hs[-1] if hs else float('inf')


def is_ceiling_valid(poly_points: Polygon, bay_h: float, ceiling_profile: CeilingProfile) -> bool:
    """
    Checks that the bay height does not exceed the ceiling height anywhere
    under the polygon footprint.
    """
    xs = [p[0] for p in poly_points]
    min_x, max_x = min(xs), max(xs)

    if bay_h > get_ceiling_height(min_x, ceiling_profile):
        return False
    if bay_h > get_ceiling_height(max_x, ceiling_profile):
        return False
    for cx, ch in zip(ceiling_profile['x'], ceiling_profile['height']):
        if min_x < cx < max_x and bay_h > ch:
            return False
    return True


# ---------------------------------------------------------------------------
# SAT POLYGON OVERLAP  (Separating Axis Theorem)
# ---------------------------------------------------------------------------

def polygons_overlap(poly1: Polygon, poly2: Polygon) -> bool:
    """
    Returns True if two convex polygons overlap (share interior area).
    Uses SAT with a small epsilon so that touching borders are legal
    but true overlaps are always caught.
    """
    def get_axes(p: Polygon) -> List[Tuple[float, float]]:
        axes = []
        for i in range(len(p)):
            p1, p2 = p[i], p[(i + 1) % len(p)]
            edge = (p2[0] - p1[0], p2[1] - p1[1])
            normal = (-edge[1], edge[0])
            length = math.hypot(*normal)
            if length > 0:
                axes.append((normal[0] / length, normal[1] / length))
        return axes

    def project(p: Polygon, axis: Tuple[float, float]) -> Tuple[float, float]:
        projs = [pt[0] * axis[0] + pt[1] * axis[1] for pt in p]
        return min(projs), max(projs)

    # Epsilon: touching borders are NOT overlapping
    EPS = 0.1
    for axis in get_axes(poly1) + get_axes(poly2):
        min1, max1 = project(poly1, axis)
        min2, max2 = project(poly2, axis)
        if max1 <= min2 + EPS or max2 <= min1 + EPS:
            return False   # Separating axis found → no overlap
    return True            # No separating axis → overlap


# ---------------------------------------------------------------------------
# POINT-IN-POLYGON  (Ray-casting)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# EDGE-EDGE INTERSECTION
# ---------------------------------------------------------------------------

def segments_intersect(
    p1: Tuple[float, float], p2: Tuple[float, float],
    p3: Tuple[float, float], p4: Tuple[float, float]
) -> bool:
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4) and
            ccw(p1, p2, p3) != ccw(p1, p2, p4))


def polygon_edges_intersect(poly1: Polygon, poly2: Polygon) -> bool:
    for i in range(len(poly1)):
        a1, a2 = poly1[i], poly1[(i + 1) % len(poly1)]
        for j in range(len(poly2)):
            b1, b2 = poly2[j], poly2[(j + 1) % len(poly2)]
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False


# ---------------------------------------------------------------------------
# FLOOR-PLAN CONTAINMENT
# ---------------------------------------------------------------------------

def is_poly_inside_floor_plan(poly: Polygon, floor_plan: Polygon) -> bool:
    """
    Checks that a convex polygon (bay or gap rectangle) lies entirely within
    the warehouse floor plan, which may be concave (L-shaped, U-shaped, etc.).

    Strategy (three-layer defence):
      1. Test every corner AND every edge midpoint of `poly`, each shifted
         slightly inward toward the centroid. This catches the case where a
         corner sits exactly on (or just beyond) a concave notch boundary.
         Edge midpoints are critical: a corner can be inside while the edge
         itself crosses a concave indentation.
      2. Check that no edge of `poly` intersects any edge of the floor plan.
         This is the definitive catch for rectangles spanning concave notches.

    The inward shift (INWARD = 0.01 = 1%) prevents ray-casting failures on
    points that lie exactly on the boundary, and is large enough to flag
    corners that are marginally outside.
    """
    INWARD = 0.01   # 1% shift toward centroid

    cx = sum(pt[0] for pt in poly) / len(poly)
    cy = sum(pt[1] for pt in poly) / len(poly)

    n = len(poly)
    for i in range(n):
        p = poly[i]
        q = poly[(i + 1) % n]

        # --- Corner test ---
        px_t = p[0] + (cx - p[0]) * INWARD
        py_t = p[1] + (cy - p[1]) * INWARD
        if not is_point_in_polygon((px_t, py_t), floor_plan):
            return False

        # --- Edge midpoint test (critical for concave floor plans) ---
        mx = (p[0] + q[0]) / 2.0
        my = (p[1] + q[1]) / 2.0
        mx_t = mx + (cx - mx) * INWARD
        my_t = my + (cy - my) * INWARD
        if not is_point_in_polygon((mx_t, my_t), floor_plan):
            return False

    # --- Edge-crossing test (final safety net) ---
    if polygon_edges_intersect(poly, floor_plan):
        return False

    return True


# ---------------------------------------------------------------------------
# POLYGON CALCULATION
# ---------------------------------------------------------------------------

def calculate_polygons(
    x: float, y: float,
    w: float, d: float,
    gap: float,
    angle_deg: float
) -> Tuple[Polygon, Polygon]:
    """
    Returns the (bay_polygon, gap_polygon) for a bay anchored at world
    position (x, y) with the given dimensions and rotation.

    Local coordinate system (BEFORE rotation):
    ┌─────────────────────────────────────┐
    │   GAP   (y = d  →  y = d + gap)    │
    ├─────────────────────────────────────┤  ← p4 ————— p3   (y = d)
    │                                     │
    │   BAY   (y = 0  →  y = d)          │
    │                                     │
    └─────────────────────────────────────┘  ← p1 ————— p2   (y = 0, anchor)
                   (x = 0)          (x = w)

    The anchor p1 is at world position (x, y). Rotation is applied around p1.
    The gap always sits on the p4–p3 side (the "top" in local space),
    regardless of rotation.

    BUG FIX vs original: the original placed the gap at y = -gap → 0
    (BELOW the bay), which is the wrong side and causes gaps to be placed
    outside the warehouse and to be completely unchecked.
    """
    rad = math.radians(angle_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)

    def transform(px: float, py: float) -> Tuple[float, float]:
        return (x + px * cos_r - py * sin_r,
                y + px * sin_r + py * cos_r)

    # Bay: bottom-left → bottom-right → top-right → top-left (local coords)
    bay_poly = [transform(px, py) for px, py in [
        (0, 0), (w, 0), (w, d), (0, d)
    ]]

    # Gap: sits ABOVE the bay in local y (p4-p3 side)
    gap_poly = [transform(px, py) for px, py in [
        (0, d), (w, d), (w, d + gap), (0, d + gap)
    ]]

    return bay_poly, gap_poly


# ---------------------------------------------------------------------------
# FULL COLLISION CHECK
# ---------------------------------------------------------------------------

def check_full_collision(
    bay_poly: Polygon,
    gap_poly: Polygon,
    static_polys: List[Polygon],
    placed_bays: List[Dict[str, Polygon]],
    floor_plan: Polygon
) -> bool:
    """
    Returns True only if the placement is fully valid:

      1. Bay AND gap must be entirely within the floor plan.
      2. Bay AND gap must not overlap any static obstacle.
      3. Bay must not overlap any previously placed bay polygon.
      4. Bay must not overlap any previously placed gap polygon.
      5. Gap must not overlap any previously placed bay polygon.
      6. Gap vs gap: ALLOWED (gaps may overlap each other).
    """
    # 1. Floor-plan containment (bay AND gap)
    if not is_poly_inside_floor_plan(bay_poly, floor_plan):
        return False
    if not is_poly_inside_floor_plan(gap_poly, floor_plan):
        return False

    # 2. Static obstacle collisions (bay AND gap)
    for obs in static_polys:
        if polygons_overlap(bay_poly, obs):
            return False
        if polygons_overlap(gap_poly, obs):
            return False

    # 3-5. Dynamic checks against already-placed bays
    for placed in placed_bays:
        p_bay = placed['bay']
        p_gap = placed['gap']

        if polygons_overlap(bay_poly, p_bay):   # rule 3: bay-bay forbidden
            return False
        if polygons_overlap(bay_poly, p_gap):   # rule 4: bay-gap forbidden
            return False
        if polygons_overlap(gap_poly, p_bay):   # rule 5: gap-bay forbidden
            return False
        # gap-gap: intentionally not checked (rule 6)

    return True