"""
BAYMAXXING
Warehouse Bay Placement Optimizer v4
Mecalux Challenge - Aggressive Node-Snapping Heuristic
"""

import csv, math, time, os, heapq
import multiprocessing as mp
from dataclasses import dataclass
from typing import List
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.cm as cm

from shapely.geometry import Polygon, box, Point
import shapely.affinity as affinity

# ══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════

@dataclass
class BayType:
    id: int
    width: float
    depth: float
    height: float
    gap: float
    n_loads: int
    price: float

    @property
    def footprint_area(self):
        return self.width * self.depth

    @property
    def price_per_load(self):
        return self.price / self.n_loads if self.n_loads else float('inf')

@dataclass
class Obstacle:
    x: float; y: float; width: float; depth: float

@dataclass
class PlacedBay:
    bay_type: BayType
    x: float; y: float; rotation: float

    def _rotate_points(self, points):
        rad = math.radians(self.rotation)
        c, s = math.cos(rad), math.sin(rad)
        return [(self.x + px*c - py*s, self.y + px*s + py*c) for px, py in points]

    def footprint_corners(self):
        w, d = self.bay_type.width, self.bay_type.depth
        return self._rotate_points([(0,0),(w,0),(w,d),(0,d)])

    def gap_corners(self):
        w, d, g = self.bay_type.width, self.bay_type.depth, self.bay_type.gap
        return self._rotate_points([(0,d),(w,d),(w,d+g),(0,d+g)])


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
    if not os.path.exists(path): return obstacles
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.lower() == 'q': continue
            parts = [x.strip() for x in line.split(',')]
            if len(parts) < 4: continue  
            try: obstacles.append(Obstacle(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError: continue
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
            bays.append(BayType(int(parts[0]), float(parts[1]), float(parts[2]),
                                float(parts[3]), float(parts[4]), int(parts[5]), float(parts[6])))
    return bays


def score(placed: List[PlacedBay], usable_area: float) -> float:
    if not placed: return float('inf')
    sum_price = sum(b.bay_type.price for b in placed)
    sum_loads = sum(b.bay_type.n_loads for b in placed)
    sum_fp    = sum(b.bay_type.footprint_area for b in placed)
    if sum_loads == 0: return float('inf')
    return (sum_price / sum_loads) ** (2.0 - min(sum_fp / usable_area, 1.0))

class WorldProxy:
    def __init__(self, placed, wh_poly, obstacles, ceiling):
        self.placed = placed; self.warehouse_poly = wh_poly
        self.obstacles = obstacles; self.ceiling = ceiling
        self.usable_area = Polygon(wh_poly).area - sum(o.width * o.depth for o in obstacles)
    def score(self): return score(self.placed, self.usable_area)


# ══════════════════════════════════════════════════════════
# HEURÍSTICA AGRESIVA: ACTIVE NODE PACKING
# ══════════════════════════════════════════════════════════

def worker_aggressive_packer(params):
    direction_mode, wh_coords, obs_data, ceiling, bay_types, time_limit = params
    start_time = time.time()
    
    wh_poly = Polygon(wh_coords)
    safe_wh = wh_poly.buffer(1.0) 
    obs_polys = [box(o.x, o.y, o.x+o.width, o.y+o.depth) for o in obs_data]
    
    bays_sorted = sorted(bay_types, key=lambda b: b.price_per_load)
    
    placed_bays = []
    placed_fps = []
    placed_gaps = []
    candidate_points = []
    visited_points = set()
    
    def add_point(x, y):
        x_rnd, y_rnd = round(x), round(y)
        if (x_rnd, y_rnd) not in visited_points:
            visited_points.add((x_rnd, y_rnd))
            if direction_mode == 'BL': prio = y_rnd * 100000 + x_rnd
            elif direction_mode == 'TR': prio = -y_rnd * 100000 - x_rnd
            elif direction_mode == 'LB': prio = x_rnd * 100000 + y_rnd
            elif direction_mode == 'RT': prio = -x_rnd * 100000 - y_rnd
            elif direction_mode == 'Y_OUT': prio = -abs(y_rnd - wh_poly.centroid.y)
            else: prio = 0
            heapq.heappush(candidate_points, (prio, float(x_rnd), float(y_rnd)))

    for x, y in wh_coords: add_point(x, y)
    for o in obs_data:
        add_point(o.x, o.y)
        add_point(o.x+o.width, o.y+o.depth)
        
    minx, miny, maxx, maxy = wh_poly.bounds
    for gx in range(int(minx), int(maxx), 2000):
        for gy in range(int(miny), int(maxy), 2000):
            add_point(gx, gy)

    while candidate_points:
        if time.time() - start_time > (time_limit - 3.0):
            break
            
        _, px, py = heapq.heappop(candidate_points)
        
        placed_here = False
        for bt in bays_sorted:
            for rot in [0, 90, 180, 270]:
                # 1. Geometría base (Pivote en px, py)
                fp = box(0, 0, bt.width, bt.depth)
                gp = box(0, bt.depth, bt.width, bt.depth + bt.gap)
                
                fp = affinity.rotate(fp, rot, origin=(0, 0))
                gp = affinity.rotate(gp, rot, origin=(0, 0))
                fp = affinity.translate(fp, px, py)
                gp = affinity.translate(gp, px, py)

                # 2. Lógica de Enfrentamiento: Probamos si rotando 180° sobre su centro
                # el pasillo (gap) coincide con uno ya puesto.
                c_x, c_y = fp.centroid.x, fp.centroid.y
                fp_flip = affinity.rotate(fp, 180, origin=(c_x, c_y))
                gp_flip = affinity.rotate(gp, 180, origin=(c_x, c_y))

                can_face = False
                for p_gp in placed_gaps:
                    if gp_flip.intersects(p_gp.buffer(-1.0)):
                        can_face = True
                        break
                
                # Definimos qué geometría y rotación usar
                if can_face:
                    f_fp, f_gp = fp_flip, gp_flip
                    f_rot = (rot + 180) % 360
                    # Cálculo trigonométrico para hallar el nuevo (x,y) de origen tras el giro de 180
                    rad = math.radians(rot)
                    f_px = px + bt.width * math.cos(rad) - bt.depth * math.sin(rad)
                    f_py = py + bt.width * math.sin(rad) + bt.depth * math.cos(rad)
                else:
                    f_fp, f_gp = fp, gp
                    f_rot = rot
                    f_px, f_py = px, py

                # 3. Validaciones
                if not safe_wh.contains(f_fp) or not safe_wh.contains(f_gp): continue
                
                f_fp_s = f_fp.buffer(-1.0)
                f_gp_s = f_gp.buffer(-1.0)
                
                if any(f_fp_s.intersects(o) or f_gp_s.intersects(o) for o in obs_polys): continue
                
                # Techo
                min_bx, _, max_bx, _ = f_fp.bounds
                fits_c = True
                for i in range(len(ceiling)):
                    cx, ch = ceiling[i]
                    nx_cx = ceiling[i+1][0] if i+1 < len(ceiling) else float('inf')
                    if max(min_bx, cx) < min(max_bx, nx_cx) and bt.height > ch:
                        fits_c = False; break
                if not fits_c: continue
                
                # Colisiones con otros ya puestos
                valid = True
                for p_fp in placed_fps:
                    if f_fp_s.intersects(p_fp) or f_gp_s.intersects(p_fp): 
                        valid = False; break
                if not valid: continue
                
                for p_gp in placed_gaps:
                    if f_fp_s.intersects(p_gp): 
                        valid = False; break
                if not valid: continue
                
                # 4. Éxito: Guardar
                placed_bays.append(PlacedBay(bt, f_px, f_py, float(f_rot)))
                placed_fps.append(f_fp)
                placed_gaps.append(f_gp)
                
                for cvx, cvy in f_fp.exterior.coords: add_point(cvx, cvy)
                for cvx, cvy in f_gp.exterior.coords: add_point(cvx, cvy)
                
                placed_here = True
                break 
            if placed_here: break 
            
    usable_area = wh_poly.area - sum(o.width*o.depth for o in obs_data)
    return placed_bays, score(placed_bays, usable_area)


def run_parallel_optimization(wh_poly_coords, obstacles, ceiling, bay_types, time_limit):
    tasks = []
    # Lanzamos exploradores gravitacionales desde todas las direcciones en paralelo
    directions = ['BL', 'TR', 'LB', 'RT', 'Y_OUT']
    for d in directions:
        tasks.append((d, wh_poly_coords, obstacles, ceiling, bay_types, time_limit))
                
    best_placed = []
    best_score_val = float('inf')
    
    # Procesamiento paralelo. Finaliza limpia y automáticamente por los timeouts internos.
    with mp.Pool(mp.cpu_count()) as pool:
        for result_placed, result_score in pool.imap_unordered(worker_aggressive_packer, tasks):
            if result_score < best_score_val:
                best_score_val = result_score
                best_placed = result_placed
                print(f"[+] Nuevo mejor score encontrado: {best_score_val:.4f} ({len(best_placed)} bays)")
                
    return best_placed


# ══════════════════════════════════════════════════════════
# I/O Y VISUALIZACIÓN
# ══════════════════════════════════════════════════════════

def write_solution(placed, path):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        for b in placed: w.writerow([b.bay_type.id, round(b.x,1), round(b.y,1), round(b.rotation,1)])

def visualize(world: WorldProxy, output_path=None):
    placed, wh_poly, obstacles, usable_area = world.placed, world.warehouse_poly, world.obstacles, world.usable_area
    fig, axes = plt.subplots(1, 2, figsize=(18, 10), gridspec_kw={'width_ratios': [3, 1]})
    ax = axes[0]
    ax.add_patch(plt.Polygon(wh_poly, fill=False, edgecolor='black', linewidth=3))

    for obs in obstacles:
        ax.add_patch(patches.Rectangle((obs.x, obs.y), obs.width, obs.depth, facecolor='#ff000033', edgecolor='red', linewidth=1.5))

    n_types = max((b.bay_type.id for b in placed), default=0) + 1
    cmap = cm.get_cmap('tab20', n_types)
    type_counts = Counter(b.bay_type.id for b in placed)
    seen_types  = set()

    for bay in placed:
        tid = bay.bay_type.id
        color = cmap(tid / max(n_types, 1))
        fp, gp = bay.footprint_corners(), bay.gap_corners()
        ax.add_patch(plt.Polygon(fp, closed=True, facecolor=color, edgecolor='#1a237e', linewidth=1.2, alpha=0.80))
        # Visualizar overlaps: Los gaps se pintan semitransparentes, la superposición intensifica el color
        ax.add_patch(plt.Polygon(gp, closed=True, facecolor=color, edgecolor='#1a237e', linewidth=0.5, alpha=0.3, linestyle='--'))
        cx, cy = sum(p[0] for p in fp) / 4, sum(p[1] for p in fp) / 4
        ax.text(cx, cy, str(tid), ha='center', va='center', fontsize=7, fontweight='bold', color='#0d0d0d')

    legend_els = []
    for bay in sorted(placed, key=lambda b: b.bay_type.id):
        tid = bay.bay_type.id
        if tid in seen_types: continue
        seen_types.add(tid)
        color = cmap(tid / max(n_types, 1))
        legend_els.append(patches.Patch(
            facecolor=color, edgecolor='#1a237e',
            label=f'T{tid} (x{type_counts.get(tid,0)}): P/L={bay.bay_type.price_per_load:.0f}'
        ))

    xs, ys = [p[0] for p in wh_poly], [p[1] for p in wh_poly]
    m = 600
    ax.set_xlim(min(xs)-m, max(xs)+m); ax.set_ylim(min(ys)-m, max(ys)+m)
    ax.set_aspect('equal')
    ax.set_title(f'Mecalux Optimizer (Aggressive) | Score={world.score():.4f}', fontsize=12, fontweight='bold')

    ax2 = axes[1]; ax2.axis('off')
    stats_text = (f"Bays placed: {len(placed)}\nCoverage: {(sum(b.bay_type.footprint_area for b in placed)/usable_area*100):.1f}%\n"
                  f"Score: {world.score():.4f}\n")
    ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes, fontsize=10, va='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax2.legend(handles=legend_els, loc='lower left', fontsize=8)

    plt.tight_layout()
    if output_path: plt.savefig(output_path, dpi=150, bbox_inches='tight')

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main(time_limit=30.0):
    print("=== Mecalux Bay Optimizer v4 (Active Node Pack) ===\n")

    cas = "Case0"

    wh_poly   = parse_warehouse(f'{cas}/warehouse.csv')
    obstacles = parse_obstacles(f'{cas}/obstacles.csv')
    ceiling   = parse_ceiling(f'{cas}/ceiling.csv')
    bay_types = parse_bay_types(f'{cas}/types_of_bays.csv')
    
    print(f"Lanzando enjambre gravitacional. Límite: {time_limit}s...")
    best_placed = run_parallel_optimization(wh_poly, obstacles, ceiling, bay_types, time_limit)
    
    world = WorldProxy(best_placed, wh_poly, obstacles, ceiling)
    print(f"\nFINAL SCORE: {world.score():.6f} | Cobertura: {sum(b.bay_type.footprint_area for b in world.placed)/world.usable_area*100:.1f}%")

    write_solution(world.placed, 'solution.csv')
    visualize(world, 'solution.png')
    
if __name__ == '__main__':
    main()
