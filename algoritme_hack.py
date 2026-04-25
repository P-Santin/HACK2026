"""
Warehouse Bay Placement Optimizer v2
Mecalux Challenge

Objective: MINIMIZE  (sum_price / sum_loads) ^ (2 - pct_area_used)
  where pct_area_used = sum_footprint / warehouse_usable_area

Gap constraint (corrected):
  - Gap zone = rectangle on the 'depth' side of a bay (y=depth..depth+gap in local coords)
  - The FOOTPRINT of bay B must NOT intersect the GAP ZONE of bay A
  - Two gap zones CAN overlap each other freely
  - A bay CAN be placed with its footprint against another bay's footprint

Key insight on the objective:
  - price/load ratio: want it LOW → tall bays (more loads per mm of width)
  - pct_area: want it HIGH → pack densely (reduces exponent toward 1)
  - Both pull in the same direction: tall, wide bays packed tightly
  - Best bay: Type 15 (4300x1000, h=5600, 16 loads, price=5320) → price/load=332.5
"""

import csv, math, random, time, os, copy
from dataclasses import dataclass
from typing import List, Tuple, Optional
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib.patches as patches


# ══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════

@dataclass
class BayType:
    id: int
    width: float    # long dimension (floor plan X in local coords)
    depth: float    # short dimension (floor plan Y in local coords)
    height: float   # vertical
    gap: float      # clearance zone on the depth side (y = depth..depth+gap)
    n_loads: int
    price: float

    @property
    def footprint_area(self):
        return self.width * self.depth

    @property
    def price_per_load(self):
        return self.price / self.n_loads


@dataclass
class Obstacle:
    x: float
    y: float
    width: float
    depth: float


@dataclass
class PlacedBay:
    bay_type: BayType
    x: float        # origin corner in world coords
    y: float
    rotation: float  # degrees (any angle)

    # ── Geometry ──────────────────────────────────────────

    def _rotate_points(self, points):
        rad = math.radians(self.rotation)
        c, s = math.cos(rad), math.sin(rad)
        return [(self.x + px*c - py*s,
                 self.y + px*s + py*c) for px, py in points]

    def footprint_corners(self):
        w, d = self.bay_type.width, self.bay_type.depth
        return self._rotate_points([(0,0),(w,0),(w,d),(0,d)])

    def gap_corners(self):
        w, d, g = self.bay_type.width, self.bay_type.depth, self.bay_type.gap
        return self._rotate_points([(0,d),(w,d),(w,d+g),(0,d+g)])

    def bounding_box(self):
        all_pts = self.footprint_corners() + self.gap_corners()
        xs, ys = zip(*all_pts)
        return min(xs), min(ys), max(xs), max(ys)

    def footprint_bb(self):
        pts = self.footprint_corners()
        xs, ys = zip(*pts)
        return min(xs), min(ys), max(xs), max(ys)


# ══════════════════════════════════════════════════════════
# PARSING
# ══════════════════════════════════════════════════════════

def parse_warehouse(path):
    coords = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = [float(x) for x in line.split(',')]
            coords.append((parts[0], parts[1]))
    return coords

def parse_obstacles(path):
    obstacles = []
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            # Ignoramos líneas vacías o la letra 'q' de tu primer ejemplo
            if not line or line.lower() == 'q': continue
            
            parts = [x.strip() for x in line.split(',')]
            if len(parts) < 4: continue  
            
            # Bloque de seguridad: si la fila tiene comas pero está vacía (ej: ",,,")
            # o tiene letras, aborta la conversión matemática y pasa a la siguiente.
            try:
                obstacles.append(Obstacle(float(parts[0]), float(parts[1]),
                                          float(parts[2]), float(parts[3])))
            except ValueError:
                continue
                
    return obstacles

def parse_ceiling(path):
    points = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = [float(x) for x in line.split(',')]
            points.append((parts[0], parts[1]))
    return sorted(points, key=lambda p: p[0])

def parse_bay_types(path):
    bays = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = [x.strip() for x in line.split(',')]
            bays.append(BayType(
                id=int(parts[0]),
                width=float(parts[1]),
                depth=float(parts[2]),
                height=float(parts[3]),
                gap=float(parts[4]),
                n_loads=int(parts[5]),
                price=float(parts[6])
            ))
    return bays


# ══════════════════════════════════════════════════════════
# GEOMETRY UTILITIES
# ══════════════════════════════════════════════════════════

def polygon_area(pts):
    n = len(pts)
    area = 0
    for i in range(n):
        j = (i+1) % n
        area += pts[i][0]*pts[j][1] - pts[j][0]*pts[i][1]
    return abs(area) / 2

def point_in_polygon(px, py, poly):
    """Ray-casting."""
    n, inside = len(poly), False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj-xi)*(py-yi)/(yj-yi)+xi):
            inside = not inside
        j = i
    return inside

def sat_overlap(poly_a, poly_b):
    """
    Separating Axis Theorem for two convex polygons.
    Returns True if they overlap (intersect).
    """
    def axes(poly):
        result = []
        n = len(poly)
        for i in range(n):
            ex = poly[(i+1)%n][0] - poly[i][0]
            ey = poly[(i+1)%n][1] - poly[i][1]
            L = math.hypot(ex, ey)
            if L < 1e-9: continue
            result.append((-ey/L, ex/L))
        return result

    def project(poly, ax):
        dots = [p[0]*ax[0] + p[1]*ax[1] for p in poly]
        return min(dots), max(dots)

    for ax in axes(poly_a) + axes(poly_b):
        lo_a, hi_a = project(poly_a, ax)
        lo_b, hi_b = project(poly_b, ax)
        if hi_a <= lo_b or hi_b <= lo_a:   # strictly no overlap
            return False
    return True

def get_ceiling_height(x, ceiling):
    h = ceiling[0][1]
    for cx, ch in ceiling:
        if x >= cx: h = ch
        else: break
    return h

def min_ceiling_over_footprint(corners, ceiling):
    xs = [p[0] for p in corners]
    lo, hi = min(xs), max(xs)
    sample_xs = [lo, hi] + [cx for cx, _ in ceiling if lo < cx < hi]
    return min(get_ceiling_height(x, ceiling) for x in sample_xs)

def warehouse_area(poly):
    return polygon_area(poly)

def obstacle_poly(obs):
    return [(obs.x, obs.y),(obs.x+obs.width, obs.y),
            (obs.x+obs.width, obs.y+obs.depth),(obs.x, obs.y+obs.depth)]


# ══════════════════════════════════════════════════════════
# OBJECTIVE FUNCTION
# ══════════════════════════════════════════════════════════

def score(placed: List[PlacedBay], usable_area: float) -> float:
    """
    Returns the value to MINIMIZE:
        (sum_price / sum_loads) ^ (2 - pct_area)
    Lower is better. Returns infinity for empty solutions.
    """
    if not placed:
        return float('inf')
    sum_price = sum(b.bay_type.price for b in placed)
    sum_loads = sum(b.bay_type.n_loads for b in placed)
    sum_fp    = sum(b.bay_type.footprint_area for b in placed)
    pct_area  = min(sum_fp / usable_area, 1.0)
    ratio     = sum_price / sum_loads
    exponent  = 2.0 - pct_area
    return ratio ** exponent

def score_delta(placed, candidate: PlacedBay, usable_area: float) -> float:
    """Score if candidate were added. Used for greedy decisions."""
    return score(placed + [candidate], usable_area)


# ══════════════════════════════════════════════════════════
# SPATIAL INDEX
# ══════════════════════════════════════════════════════════

class SpatialGrid:
    def __init__(self, cell_size=2000):
        self.cs = cell_size
        self.grid = {}

    def _cells_for_bb(self, x1, y1, x2, y2):
        cx1, cy1 = int(x1//self.cs), int(y1//self.cs)
        cx2, cy2 = int(x2//self.cs), int(y2//self.cs)
        return [(cx, cy) for cx in range(cx1, cx2+1) for cy in range(cy1, cy2+1)]

    def add(self, bay: PlacedBay):
        for cell in self._cells_for_bb(*bay.bounding_box()):
            self.grid.setdefault(cell, []).append(bay)

    def remove(self, bay: PlacedBay):
        for cell in self._cells_for_bb(*bay.bounding_box()):
            if cell in self.grid:
                self.grid[cell] = [b for b in self.grid[cell] if b is not bay]

    def candidates(self, bay: PlacedBay):
        seen, result = set(), []
        for cell in self._cells_for_bb(*bay.bounding_box()):
            for b in self.grid.get(cell, []):
                if id(b) not in seen:
                    seen.add(id(b))
                    result.append(b)
        return result


# ══════════════════════════════════════════════════════════
# VALIDATOR (fast, uses spatial index)
# ══════════════════════════════════════════════════════════

class World:
    """Holds all placed bays + fast validity checking."""

    def __init__(self, warehouse_poly, obstacles, ceiling):
        self.warehouse_poly = warehouse_poly
        self.obstacles      = obstacles
        self.ceiling        = ceiling
        self.obs_polys      = [obstacle_poly(o) for o in obstacles]
        self.placed: List[PlacedBay] = []
        self.grid = SpatialGrid()
        self.usable_area = warehouse_area(warehouse_poly) - sum(
            o.width * o.depth for o in obstacles)

    # ── Core validity ─────────────────────────────────────

    def is_valid(self, bay: PlacedBay) -> bool:
        fp  = bay.footprint_corners()
        gp  = bay.gap_corners()

        # 1a. La huella física no puede salir del almacén
        for px, py in fp:
            if not point_in_polygon(px, py, self.warehouse_poly):
                return False

        # 1b. NUEVO: El gap TAMPOCO puede salir del almacén
        for px, py in gp:
            if not point_in_polygon(px, py, self.warehouse_poly):
                return False

        # 2. Footprint doesn't overlap obstacles
        for op in self.obs_polys:
            if sat_overlap(fp, op):
                return False
            
            if sat_overlap(gp, op):
                return False

        # 3. Bay height fits ceiling over entire footprint
        if bay.bay_type.height > min_ceiling_over_footprint(fp, self.ceiling):
            return False

        # 4. Check against each nearby placed bay
        for other in self.grid.candidates(bay):
            other_fp  = other.footprint_corners()
            other_gap = other.gap_corners()

            # 4a. Footprints must not overlap
            if sat_overlap(fp, other_fp):
                return False

            # 4b. bay's footprint must not enter other's gap zone
            if sat_overlap(fp, other_gap):
                return False

            # 4c. other's footprint must not enter bay's gap zone
            if sat_overlap(other_fp, gp):
                return False

        return True

    def add(self, bay: PlacedBay):
        self.placed.append(bay)
        self.grid.add(bay)

    def remove(self, bay: PlacedBay):
        self.placed.remove(bay)
        self.grid.remove(bay)

    def score(self) -> float:
        return score(self.placed, self.usable_area)

    def validate_all(self):
        """Full re-validation of solution (for final check)."""
        tmp = World(self.warehouse_poly, self.obstacles, self.ceiling)
        for i, bay in enumerate(self.placed):
            if not tmp.is_valid(bay):
                return False, f"Bay {i} (type {bay.bay_type.id}) invalid"
            tmp.add(bay)
        return True, "OK"


# ══════════════════════════════════════════════════════════
# OPTIMIZER
# ══════════════════════════════════════════════════════════

class Optimizer:

    ROTATIONS = [0, 90, 180, 270]

    def __init__(self, warehouse_poly, obstacles, ceiling, bay_types):
        self.wh_poly    = warehouse_poly
        self.obstacles  = obstacles
        self.ceiling    = ceiling
        self.bay_types  = bay_types

        xs = [p[0] for p in warehouse_poly]
        ys = [p[1] for p in warehouse_poly]
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)

        # Sorted orders for different strategies
        # Primary: best price/load (minimize ratio)
        self.by_value = sorted(bay_types, key=lambda b: b.price_per_load)
        # Secondary: largest footprint first (maximize area coverage)
        self.by_area  = sorted(bay_types, key=lambda b: -b.footprint_area)
        # Mixed: balance ratio + area
        self.by_mixed = sorted(bay_types,
            key=lambda b: b.price_per_load / (b.footprint_area ** 0.5))

    # ── Helpers ───────────────────────────────────────────

    def try_place(self, world: World, bt: BayType, x, y, rot) -> Optional[PlacedBay]:
        c = PlacedBay(bt, x, y, rot)
        return c if world.is_valid(c) else None

    def best_place(self, world: World, x, y) -> Optional[PlacedBay]:
        """Búsqueda Adaptativa: Prueba rotaciones estándar; si fallan, prueba rotaciones arbitrarias."""
        best, best_s = None, float('inf')
        
        for bt in self.by_value:
            encajado_ortogonal = False
            
            # 1. Intentar las rotaciones principales (0, 90, 180, 270)
            for rot in self.ROTATIONS:
                c = self.try_place(world, bt, x, y, rot)
                if c:
                    s = score_delta(world.placed, c, world.usable_area)
                    if s < best_s:
                        best_s, best = s, c
                    encajado_ortogonal = True
            
            # 2. TU LÓGICA: Si no se pudo colocar ortogonalmente, probamos ángulos arbitrarios
            if not encajado_ortogonal:
                # Generamos ángulos de exploración (ej. cada 15 grados, o totalmente aleatorios)
                # Usamos una lista fija de ángulos intermedios para ser rápidos y precisos
                angulos_extra = [15, 30, 45, 60, 75, 105, 120, 135, 150, 165]
                
                for rot in angulos_extra:
                    c = self.try_place(world, bt, x, y, rot)
                    if c:
                        s = score_delta(world.placed, c, world.usable_area)
                        if s < best_s:
                            best_s, best = s, c
                            
        return best

    # ── Anchor positions ─────────────────────────────────

    def anchor_positions(self, world: World):
        """
        Generate candidate placement positions:
        - Warehouse corners
        - Obstacle corners
        - Corners of placed bay footprints and gap zones
        - Points just beyond each bay edge (snapping)
        """
        pts = list(self.wh_poly)
        for obs in self.obstacles:
            pts += obstacle_poly(obs)
        for bay in world.placed:
            fp = bay.footprint_corners()
            gp = bay.gap_corners()
            pts += fp + gp
            # Also add points "just past" each edge of the bay footprint+gap combined
            all_c = fp + gp
            for i in range(len(fp)):
                j = (i+1) % len(fp)
                pts.append(fp[j])  # corner itself
        # Deduplicate
        seen, unique = set(), []
        for p in pts:
            k = (round(p[0]/10)*10, round(p[1]/10)*10)
            if k not in seen:
                seen.add(k)
                unique.append(p)
        return [(px, py) for px, py in unique
                if point_in_polygon(px, py, self.wh_poly)]

    # ── Phase 1: Grid greedy ──────────────────────────────

    def grid_fill(self, world: World, step=500):
        """Scan grid; at each free point try to place best scoring bay."""
        y = self.min_y
        while y <= self.max_y:
            x = self.min_x
            while x <= self.max_x:
                if point_in_polygon(x, y, self.wh_poly):
                    # Quick occupancy check
                    dummy = PlacedBay(self.bay_types[0], x, y, 0)
                    nearby = world.grid.candidates(dummy)
                    occupied = any(point_in_polygon(x, y, b.footprint_corners())
                                   for b in nearby)
                    if not occupied:
                        c = self.best_place(world, x, y)
                        if c:
                            world.add(c)
                x += step
            y += step

    # ── Phase 2: Anchor fill ──────────────────────────────

    def anchor_fill(self, world: World):
        """Fill from anchor positions (bay edges, walls, obstacles)."""
        changed = True
        while changed:
            changed = False
            for px, py in self.anchor_positions(world):
                dummy = PlacedBay(self.bay_types[0], px, py, 0)
                nearby = world.grid.candidates(dummy)
                occupied = any(point_in_polygon(px, py, b.footprint_corners())
                               for b in nearby)
                if occupied:
                    continue
                c = self.best_place(world, px, py)
                if c:
                    world.add(c)
                    changed = True

    # ── Phase 3: Row packing ──────────────────────────────

    def row_pack(self, world: World):
        """
        Pack bays in axis-aligned rows.
        For each horizontal strip, fill left-to-right with best bay types.
        Try both orientations (rows along X and rows along Y).
        """
        for orient in ['x', 'y']:
            y = self.min_y
            while y < self.max_y:
                x = self.min_x
                row_h = 0
                while x < self.max_x:
                    if not point_in_polygon(x + 1, y + 1, self.wh_poly):
                        x += 200
                        continue
                    placed = False
                    for bt in self.by_value:
                        for rot in (self.ROTATIONS if orient == 'x' else [90, 270, 0, 180]):
                            c = self.try_place(world, bt, x, y, rot)
                            if c:
                                world.add(c)
                                _, _, bx2, by2 = c.bounding_box()
                                row_h = max(row_h, by2 - y)
                                x = bx2
                                placed = True
                                break
                        if placed: break
                    if not placed:
                        x += 200
                y += row_h if row_h > 0 else 400

    # ── Phase 4: Local search ─────────────────────────────

    def local_search(self, world: World, time_limit=20.0):
        """
        Improvement loop:
          - Strategy A: swap a bad bay for a better-scoring one
          - Strategy B: remove one bay, try to insert 2+ better ones nearby
          - Strategy C: change rotation of a bay to open space for new one
        Accepts moves that improve the objective score.
        """
        start   = time.time()
        best_sc = world.score()
        no_improve = 0

        print(f"  Local search start: score={best_sc:.4f}, n={len(world.placed)}")

        while time.time() - start < time_limit and no_improve < 60:
            strat = random.random()
            improved = False

            # ── Strategy A: replace one bay with a better-scoring type ──
            if strat < 0.35 and world.placed:
                bay = random.choice(world.placed)
                world.remove(bay)
                best_c, best_s = None, world.score()
                for bt in self.by_value:
                    for rot in self.ROTATIONS:
                        c = self.try_place(world, bt, bay.x, bay.y, rot)
                        if c:
                            s = score(world.placed + [c], world.usable_area)
                            if s < best_s:
                                best_s, best_c = s, c
                if best_c and best_s < best_sc:
                    world.add(best_c)
                    best_sc = best_s
                    improved = True
                else:
                    world.add(bay)

            # ── Strategy B: remove worst bay, try to fill gap with 2+ bays ──
            elif strat < 0.70 and world.placed:
                # "Worst" = contributes most to the score (high price/load)
                worst = max(world.placed,
                            key=lambda b: b.bay_type.price_per_load)
                ox, oy = worst.x, worst.y
                world.remove(worst)
                pre_sc = world.score()

                added = []
                offsets = [(dx, dy) for dx in [0, 100, -100, 200, -200, 300]
                                    for dy in [0, 100, -100, 200, -200, 300]]
                for bt in self.by_value:
                    for rot in self.ROTATIONS:
                        for dx, dy in offsets:
                            nx, ny = ox+dx, oy+dy
                            if not point_in_polygon(nx, ny, self.wh_poly):
                                continue
                            c = self.try_place(world, bt, nx, ny, rot)
                            if c:
                                world.add(c)
                                added.append(c)
                                break
                        else: continue
                        break
                    if len(added) >= 2:
                        break

                new_sc = world.score()
                if new_sc < best_sc:
                    best_sc = new_sc
                    improved = True
                else:
                    # Revert
                    for a in added: world.remove(a)
                    world.add(worst)

            # ── Strategy C: rotate + fill ──
            else:
                if not world.placed: continue
                bay = random.choice(world.placed)
                world.remove(bay)
                best_combo = None
                best_s = world.score()

                for rot in self.ROTATIONS:
                    if rot == bay.rotation: continue
                    c = self.try_place(world, bay.bay_type, bay.x, bay.y, rot)
                    if not c: continue
                    world.add(c)
                    # Try to fit one extra bay near the new position
                    _, _, cx2, cy2 = c.bounding_box()
                    for bt2 in self.by_value:
                        for r2 in self.ROTATIONS:
                            for nx, ny in [(cx2, bay.y), (bay.x, cy2),
                                           (cx2+50, bay.y), (bay.x, cy2+50)]:
                                extra = self.try_place(world, bt2, nx, ny, r2)
                                if extra:
                                    s = score(world.placed + [extra], world.usable_area)
                                    if s < best_s:
                                        best_s, best_combo = s, (c, extra)
                    world.remove(c)

                if best_combo and best_s < best_sc:
                    for bc in best_combo: world.add(bc)
                    best_sc = best_s
                    improved = True
                else:
                    world.add(bay)

            no_improve = 0 if improved else no_improve + 1

        elapsed = time.time() - start
        print(f"  Local search end:   score={world.score():.4f}, "
              f"n={len(world.placed)}, t={elapsed:.1f}s, stagnation={no_improve}")

    # ── Main optimize ─────────────────────────────────────

    def optimize(self, time_limit=45.0) -> World:
        world = World(self.wh_poly, self.obstacles, self.ceiling)

        print("Phase 1: Row packing (value-first)...")
        self.row_pack(world)
        print(f"  n={len(world.placed)}, score={world.score():.4f}")

        print("Phase 2: Grid fill (step=300)...")
        self.grid_fill(world, step=300)
        print(f"  n={len(world.placed)}, score={world.score():.4f}")

        print("Phase 3: Anchor fill...")
        self.anchor_fill(world)
        print(f"  n={len(world.placed)}, score={world.score():.4f}")

        ls_time = max(10.0, time_limit - 15.0)
        print(f"Phase 4: Local search ({ls_time:.0f}s)...")
        self.local_search(world, time_limit=ls_time)

        print("Phase 5: Final anchor fill...")
        self.anchor_fill(world)
        print(f"  n={len(world.placed)}, score={world.score():.4f}")

        return world


# ══════════════════════════════════════════════════════════
# OUTPUT & VISUALIZATION
# ══════════════════════════════════════════════════════════

def write_solution(placed, path):
    #os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Id', 'X', 'Y', 'Rotation'])
        for b in placed:
            w.writerow([b.bay_type.id, round(b.x,1), round(b.y,1), round(b.rotation,1)])
    print(f"Solution written: {path}")

def visualize(world: World, output_path=None):
    placed       = world.placed
    wh_poly      = world.warehouse_poly
    obstacles    = world.obstacles
    usable_area  = world.usable_area

    fig, axes = plt.subplots(1, 2, figsize=(18, 10),
                             gridspec_kw={'width_ratios': [3, 1]})
    ax = axes[0]

    # Warehouse outline
    ax.add_patch(plt.Polygon(wh_poly, fill=False, edgecolor='black', linewidth=3))

    # Obstacles
    for obs in obstacles:
        ax.add_patch(patches.Rectangle(
            (obs.x, obs.y), obs.width, obs.depth,
            facecolor='#ff000033', edgecolor='red', linewidth=1.5))

    # Palette
    import matplotlib.cm as cm
    n_types = max((b.bay_type.id for b in placed), default=0) + 1
    cmap = cm.get_cmap('tab20', n_types)

    # Recuento blindado
    from collections import Counter
    type_counts = Counter(b.bay_type.id for b in placed)
    seen_types  = set()

    for bay in placed:
        tid   = bay.bay_type.id
        color = cmap(tid / max(n_types, 1))
        fp    = bay.footprint_corners()
        gp    = bay.gap_corners()

        # Footprint
        fp_patch = plt.Polygon(fp, closed=True, facecolor=color,
                                edgecolor='#1a237e', linewidth=1.2, alpha=0.80)
        ax.add_patch(fp_patch)

        # Gap zone
        gp_patch = plt.Polygon(gp, closed=True, facecolor=color,
                                edgecolor='#1a237e', linewidth=0.5,
                                alpha=0.18, linestyle='--')
        ax.add_patch(gp_patch)

        # Label
        cx = sum(p[0] for p in fp) / 4
        cy = sum(p[1] for p in fp) / 4
        ax.text(cx, cy, str(tid), ha='center', va='center',
                fontsize=7, fontweight='bold', color='#0d0d0d')

    # Legend
    legend_els = []
    for bay in sorted(placed, key=lambda b: b.bay_type.id):
        tid = bay.bay_type.id
        if tid in seen_types: continue
        seen_types.add(tid)
        bt = bay.bay_type
        color = cmap(tid / max(n_types, 1))
        
        # USO DE .get() PARA EVITAR KEYERRORS Y CARACTERES ASCII SEGUROS
        cnt = type_counts.get(tid, 0)
        legend_els.append(patches.Patch(
            facecolor=color, edgecolor='#1a237e',
            label=f'T{tid} (x{cnt}): {int(bt.width)}x{int(bt.depth)} '
                  f'h={int(bt.height)} gap={int(bt.gap)} '
                  f'loads={bt.n_loads} EUR {bt.price:.0f} [EUR/load={bt.price_per_load:.0f}]'
        ))

    xs = [p[0] for p in wh_poly]; ys = [p[1] for p in wh_poly]
    m = 600
    ax.set_xlim(min(xs)-m, max(xs)+m)
    ax.set_ylim(min(ys)-m, max(ys)+m)
    ax.set_aspect('equal')
    ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)')
    ax.grid(True, alpha=0.2, linestyle='--')

    # Stats
    sc    = world.score()
    sp    = sum(b.bay_type.price for b in placed)
    sl    = sum(b.bay_type.n_loads for b in placed)
    sfp   = sum(b.bay_type.footprint_area for b in placed)
    pct   = sfp / usable_area * 100 if usable_area else 0
    exp   = 2.0 - (sfp/usable_area) if usable_area else 2.0
    ax.set_title(
        f'Mecalux Optimizer  |  {len(placed)} bays  |  {sl} loads  |  '
        f'EUR {sp:,.0f}  |  {pct:.1f}% area  |  score={sc:.4f}',
        fontsize=11, fontweight='bold', pad=8)

    # Right panel
    ax2 = axes[1]
    ax2.axis('off')
    ax2.add_patch(patches.FancyBboxPatch((0,0), 1, 1,
        boxstyle='round,pad=0.05', facecolor='#f5f5f5', edgecolor='#cccccc'))

    stats_text = (
        f"SOLUTION SUMMARY\n"
        f"{'-'*28}\n"
        f"Bays placed:    {len(placed)}\n"
        f"Total loads:    {sl}\n"
        f"Total price:    EUR {sp:,.0f}\n"
        f"Price/load:     EUR {sp/sl:.1f}\n"
        f"Area used:      {sfp/1e6:.1f} m2\n"
        f"Usable area:    {usable_area/1e6:.1f} m2\n"
        f"Coverage:       {pct:.1f}%\n"
        f"Exponent:       {exp:.3f}\n"
        f"{'-'*28}\n"
        f"SCORE:          {sc:.4f}\n"
        f"(lower = better)\n"
        f"{'-'*28}\n"
        f"TYPE BREAKDOWN\n"
    )
    for tid, cnt in sorted(type_counts.items()):
        # Bloque Try-Except por seguridad adicional
        try:
            bt = next(b.bay_type for b in placed if b.bay_type.id == tid)
            stats_text += f"  T{tid}: x{cnt} -> {cnt*bt.n_loads} loads\n"
        except StopIteration:
            continue

    ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes,
             fontsize=9, va='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax2.legend(handles=legend_els, loc='lower left', fontsize=7.5,
               framealpha=0.9, title='Bay Types')

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Visualization saved: {output_path}")
    return fig


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main(warehouse_path, obstacles_path, ceiling_path, bay_types_path,
         output_csv, output_img, time_limit=30.0):

    print("=== Warehouse Bay Optimizer v2 ===\n")

    wh_poly   = parse_warehouse(warehouse_path)
    obstacles = parse_obstacles(obstacles_path)
    ceiling   = parse_ceiling(ceiling_path)
    bay_types = parse_bay_types(bay_types_path)

    print(f"Warehouse: {len(wh_poly)} vertices, area={warehouse_area(wh_poly)/1e6:.1f}m²")
    print(f"Obstacles: {len(obstacles)}")
    print(f"Ceiling:   {ceiling}")
    print(f"Bay types: {len(bay_types)}")
    for bt in bay_types:
        print(f"  T{bt.id:2d}: {int(bt.width)}×{int(bt.depth)} "
              f"h={int(bt.height)} gap={int(bt.gap)} "
              f"loads={bt.n_loads} price={bt.price} €/load={bt.price_per_load:.1f}")
    print()

    random.seed(42)
    optimizer = Optimizer(wh_poly, obstacles, ceiling, bay_types)
    world     = optimizer.optimize(time_limit=time_limit)

    ok, msg = world.validate_all()
    print(f"\nValidation: {'✓ VALID' if ok else '✗ INVALID — ' + msg}")

    sc = world.score()
    sp = sum(b.bay_type.price for b in world.placed)
    sl = sum(b.bay_type.n_loads for b in world.placed)
    sf = sum(b.bay_type.footprint_area for b in world.placed)
    print(f"\n=== FINAL RESULTS ===")
    print(f"  Score (minimize):  {sc:.6f}")
    print(f"  Bays:              {len(world.placed)}")
    print(f"  Loads:             {sl}")
    print(f"  Price:             €{sp:,.0f}")
    print(f"  Coverage:          {sf/world.usable_area*100:.1f}%")
    print(f"  Type breakdown:    {dict(sorted(Counter(b.bay_type.id for b in world.placed).items()))}")

    #os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    write_solution(world.placed, output_csv)
    visualize(world, output_img)
    print("\nDone!")


if __name__ == '__main__':
    # Las rutas se han actualizado para apuntar al directorio local actual.
    # Asegúrate de tener los archivos CSV en la misma carpeta que el script.
    main(
        warehouse_path = 'warehouse.csv',
        obstacles_path = 'obstacles.csv',
        ceiling_path   = 'ceiling.csv',
        bay_types_path = 'types_of_bays.csv',
        output_csv     = 'solution.csv',
        output_img     = 'solution.png',
        time_limit     = 45.0,
    )