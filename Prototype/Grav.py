import math
from typing import List, Tuple, Optional, Dict, Any
from data_collection import Layout
from validator import calculate_polygons, is_ceiling_valid, check_full_collision

Polygon = List[Tuple[float, float]]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _is_valid_placement(
    cx: float, cy: float,
    w: float, d: float, h_bay: float, gap: float,
    angle_deg: float,
    layout: Layout,
    placed_bays: List[Dict[str, Polygon]],
    static_polys: List[Polygon],
    floor_plan: Polygon
) -> Tuple[bool, Optional[Polygon], Optional[Polygon]]:
    """
    Single validity gate: computes polygons and runs the full check.
    Returns (is_valid, bay_poly, gap_poly).
    """
    bay_poly, gap_poly = calculate_polygons(cx, cy, w, d, gap, angle_deg)
    valid = (
        is_ceiling_valid(bay_poly, h_bay, layout.ceiling) and
        is_ceiling_valid(gap_poly, h_bay, layout.ceiling) and
        check_full_collision(bay_poly, gap_poly, static_polys, placed_bays, floor_plan)
    )
    return valid, bay_poly, gap_poly


# ---------------------------------------------------------------------------
# GRAVITY PLACER
# ---------------------------------------------------------------------------

def place_shelf_gravity(
    bay_id: int,
    layout: Layout,
    angle_deg: float,
    start_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    placed_bays: List[Dict[str, Polygon]],
    static_polys: List[Polygon],
    floor_plan: Polygon
) -> Tuple[Optional[Polygon], Optional[Polygon], Optional[float], Optional[float]]:
    """
    Simulates a bay 'falling' from start_pos toward target_pos.

    The bay slides along the straight line from start → target and comes
    to rest at the LAST valid position found along that trajectory — i.e.,
    as close to the target (the 'floor') as possible, just like gravity.

    Algorithm (two-phase for speed + precision):
      Phase 1 — Coarse scan: step along the line with a stride proportional
                 to the bay's smallest dimension. Track the last valid step.
      Phase 2 — Fine scan: re-scan a ±1 coarse-step window around the last
                 valid coarse position with a much finer stride to find the
                 exact rest position.

    This correctly implements directional gravity and replaces the previous
    stub that ignored start_pos and target_pos entirely.
    """
    specs = layout.bays[bay_id]
    w, d, h_bay, gap = specs['width'], specs['depth'], specs['height'], specs['gap']

    sx, sy = start_pos
    tx, ty = target_pos
    dx, dy = tx - sx, ty - sy
    total_dist = math.hypot(dx, dy)

    if total_dist < 1e-6:
        return None, None, None, None

    # Unit direction vector toward target
    ux, uy = dx / total_dist, dy / total_dist

    # Stride sizing: coarse stride is ~40% of the smaller bay dimension so we
    # never skip a valid slot entirely. Fine stride is ~4% for precision.
    min_dim = min(w, d)
    coarse_step = max(50.0, min_dim * 0.40)
    fine_step   = max(5.0,  min_dim * 0.04)

    # ── Phase 1: coarse scan ────────────────────────────────────────────────
    last_valid_t: Optional[float] = None
    t = 0.0
    while t <= total_dist:
        cx, cy = sx + ux * t, sy + uy * t
        valid, _, _ = _is_valid_placement(
            cx, cy, w, d, h_bay, gap, angle_deg,
            layout, placed_bays, static_polys, floor_plan
        )
        if valid:
            last_valid_t = t
        t += coarse_step

    if last_valid_t is None:
        return None, None, None, None

    # ── Phase 2: fine scan around last valid coarse hit ─────────────────────
    t_lo = max(0.0,         last_valid_t - coarse_step)
    t_hi = min(total_dist,  last_valid_t + coarse_step)

    best_x: Optional[float] = None
    best_y: Optional[float] = None
    best_bay: Optional[Polygon] = None
    best_gap: Optional[Polygon] = None

    t = t_lo
    while t <= t_hi:
        cx, cy = sx + ux * t, sy + uy * t
        valid, bay_poly, gap_poly = _is_valid_placement(
            cx, cy, w, d, h_bay, gap, angle_deg,
            layout, placed_bays, static_polys, floor_plan
        )
        if valid:
            # Keep updating: we want the LAST (deepest) valid position
            best_x, best_y = cx, cy
            best_bay, best_gap = bay_poly, gap_poly
        t += fine_step

    return best_bay, best_gap, best_x, best_y


# ---------------------------------------------------------------------------
# SMART RASTER-SCAN FALLBACK
# ---------------------------------------------------------------------------

def place_shelf_smart(
    bay_id: int,
    layout: Layout,
    angle_deg: float,
    placed_bays: List[Dict[str, Polygon]],
    static_polys: List[Polygon],
    floor_plan: Polygon
) -> Tuple[Optional[Polygon], Optional[Polygon], Optional[float], Optional[float]]:
    """
    Fallback placer: exhaustive raster scan of the warehouse bounding box.

    Used when the gravity placer finds no valid position along its specific
    trajectory. Scans with a coarse stride (fast), then compacts the found
    position down-left with a fine stride (tight packing).

    Stride is capped to the bay's smallest dimension so no valid slot is
    skipped — fixing the original hardcoded stride_coarse=300 bug.
    """
    specs = layout.bays[bay_id]
    w, d, h_bay, gap = specs['width'], specs['depth'], specs['height'], specs['gap']

    xs = [p[0] for p in floor_plan]
    ys = [p[1] for p in floor_plan]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    min_dim = min(w, d)
    stride_coarse = max(100.0, min_dim * 0.5)
    stride_fine   = max(10.0,  min_dim * 0.05)

    def _check(cx, cy):
        return _is_valid_placement(
            cx, cy, w, d, h_bay, gap, angle_deg,
            layout, placed_bays, static_polys, floor_plan
        )

    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            valid, bay_poly, gap_poly = _check(x, y)
            if valid:
                bx, by = x, y

                # Compact leftward (−x)
                cx = bx - stride_fine
                while cx >= min_x:
                    v, bp, gp = _check(cx, by)
                    if v:
                        bx, bay_poly, gap_poly = cx, bp, gp
                        cx -= stride_fine
                    else:
                        break

                # Compact downward (−y)
                cy = by - stride_fine
                while cy >= min_y:
                    v, bp, gp = _check(bx, cy)
                    if v:
                        by, bay_poly, gap_poly = cy, bp, gp
                        cy -= stride_fine
                    else:
                        break

                return bay_poly, gap_poly, bx, by

            x += stride_coarse
        y += stride_coarse

    return None, None, None, None


# ---------------------------------------------------------------------------
# FITNESS FUNCTION
# ---------------------------------------------------------------------------

def calculate_fitness(placed_data: List[Dict[str, Any]], layout: Layout) -> float:
    """
    Minimisation objective:
        ( sum(prices) / sum(loads) ) ^ ( 2 − percentage_area_used )

    percentage_area_used = sum of bay footprint areas / warehouse floor area.
    Gap area is intentionally EXCLUDED from the numerator (as specified).

    Lower fitness is better. Returns inf for empty solutions.
    """
    if not placed_data:
        return float('inf')

    # Warehouse area via Shoelace
    fp = layout.floor_plan
    n = len(fp)
    area_almacen = 0.0
    for i in range(n):
        p1, p2 = fp[i], fp[(i + 1) % n]
        area_almacen += p1[0] * p2[1] - p2[0] * p1[1]
    area_almacen = abs(area_almacen) / 2.0

    total_price = sum(d['price']  for d in placed_data)
    total_load  = sum(d['n_loads'] for d in placed_data)
    # Gap area excluded: only bay footprint (width × depth)
    used_area   = sum(d['width'] * d['depth'] for d in placed_data)

    if total_load == 0:
        return float('inf')

    pct_used = (used_area / area_almacen) if area_almacen > 0 else 0.0
    base     = max(total_price / total_load, 1.0)
    exponent = 2.0 - pct_used

    return base ** exponent