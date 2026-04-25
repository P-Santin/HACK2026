import random
import csv
import os
from typing import List, Tuple, Any, Dict

from data_collection import cargar_datos_logistica, Layout, visualizar_layout_completo
from validator import calculate_polygons, is_ceiling_valid, check_full_collision
from heuristic import evaluate_placement_score

Polygon = List[Tuple[float, float]]

# ---------------------------------------------------------------------------
# UTILITY & FITNESS
# ---------------------------------------------------------------------------

def _warehouse_bounds(layout: Layout) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in layout.floor_plan]
    ys = [p[1] for p in layout.floor_plan]
    return min(xs), max(xs), min(ys), max(ys)

def _warehouse_area(layout: Layout) -> float:
    fp = layout.floor_plan
    n  = len(fp)
    area = 0.0
    for i in range(n):
        p1, p2 = fp[i], fp[(i + 1) % n]
        area += p1[0] * p2[1] - p2[0] * p1[1]
    return abs(area) / 2.0

def calculate_fitness(placed_data: List[Dict[str, Any]], layout: Layout) -> float:
    """
    Minimisation objective: ( sum(prices) / sum(loads) ) ^ ( 2 − percentage_area_used )
    Lower fitness is better.
    """
    if not placed_data:
        return float('inf')

    area_almacen = _warehouse_area(layout)
    total_price  = sum(d['price']  for d in placed_data)
    total_load   = sum(d['n_loads'] for d in placed_data)
    used_area    = sum(d['width'] * d['depth'] for d in placed_data)

    if total_load == 0:
        return float('inf')

    pct_used = (used_area / area_almacen) if area_almacen > 0 else 0.0
    base     = max(total_price / total_load, 1.0)
    exponent = 2.0 - pct_used

    return base ** exponent


# ---------------------------------------------------------------------------
# CORE PLACEMENT ENGINE (Heuristic)
# ---------------------------------------------------------------------------

def heuristic_fill(
    layout: Layout,
    catalog_shelves: List[Dict],
    static_polys: List[Polygon],
    placed_bays_polys: List[Dict],
    shelves_data: List[Dict],
    bays_format: List[List]
) -> Tuple[List[Dict], List[Dict], List[List]]:
    """
    Fills the warehouse using the Maximal Adjacency heuristic. 
    Accepts existing placements so it can be used for both Construction and Local Search.
    """
    # Clone arrays to avoid mutating the originals during local search trials
    current_polys  = placed_bays_polys[:]
    current_data   = shelves_data[:]
    current_format = bays_format[:]

    sorted_catalog = sorted(catalog_shelves, key=lambda s: s['width'] * s['depth'], reverse=True)
    min_x, max_x, min_y, max_y = _warehouse_bounds(layout)

    while True:
        # Generate Candidate Points: Corners of walls, obstacles, and placed bays
        candidate_points = set()
        for p in layout.floor_plan: candidate_points.add((p[0], p[1]))
        for obs in static_polys:
            for p in obs: candidate_points.add((p[0], p[1]))
        for p_bay in current_polys:
            for p in p_bay['bay']: candidate_points.add((p[0], p[1]))
            
        if not candidate_points:
            candidate_points.add((min_x, min_y))

        best_score = -1
        best_placement = None
        best_shelf = None

        # GRASP Randomness: Shuffle top candidates to vary layouts slightly
        rcl_size = min(3, len(sorted_catalog))
        candidates_to_try = sorted_catalog[:rcl_size]
        random.shuffle(candidates_to_try)
        candidates_to_try += sorted_catalog[rcl_size:]

        for shelf in candidates_to_try:
            w, d, h_bay, gap = shelf['width'], shelf['depth'], shelf['height'], shelf['gap']

            for cx, cy in candidate_points:
                for angle in [0, 90, 180, 270]:
                    bay_poly, gap_poly = calculate_polygons(cx, cy, w, d, gap, angle)

                    valid = (
                        is_ceiling_valid(bay_poly, h_bay, layout.ceiling) and
                        is_ceiling_valid(gap_poly, h_bay, layout.ceiling) and
                        check_full_collision(bay_poly, gap_poly, static_polys, current_polys, layout.floor_plan)
                    )

                    if valid:
                        score = evaluate_placement_score(bay_poly, gap_poly, current_polys, layout.floor_plan)
                        
                        if score > best_score:
                            best_score = score
                            best_placement = (bay_poly, gap_poly, cx, cy, angle)
                            best_shelf = shelf

            if best_placement is not None:
                break # Shelf placed, restart loop

        if best_placement is None:
            break # Warehouse is completely full

        # Apply placement
        bp, gp, px, py, p_angle = best_placement
        current_polys.append({'bay': bp, 'gap': gp})
        current_data.append(best_shelf)
        current_format.append([best_shelf['id'], px, py, p_angle])

    return current_polys, current_data, current_format


# ---------------------------------------------------------------------------
# LOCAL SEARCH
# ---------------------------------------------------------------------------

def local_search(
    placed_bays_polys: List[Dict],
    shelves_data:      List[Dict],
    bays_format:       List[List],
    layout:            Layout,
    catalog_shelves:   List[Dict],
    static_polys:      List[Polygon],
    ls_iterations:     int = 15
) -> Tuple[List[Dict], List[Dict], List[List], float]:
    """
    Removes the least efficient bay and uses `heuristic_fill` to pack new bays 
    into the newly freed space.
    """
    best_polys   = placed_bays_polys[:]
    best_data    = shelves_data[:]
    best_format  = bays_format[:]
    best_fitness = calculate_fitness(best_data, layout)

    for ls_iter in range(ls_iterations):
        if not best_data:
            break

        # Find the worst performing bay based on price-to-load ratio
        worst_idx = max(
            range(len(best_data)),
            key=lambda i: best_data[i]['price'] / max(best_data[i]['n_loads'], 1)
        )

        trial_polys  = best_polys[:worst_idx]  + best_polys[worst_idx + 1:]
        trial_data   = best_data[:worst_idx]   + best_data[worst_idx + 1:]
        trial_format = best_format[:worst_idx] + best_format[worst_idx + 1:]

        # Attempt to aggressively repack the freed space with our heuristic engine
        trial_polys, trial_data, trial_format = heuristic_fill(
            layout, catalog_shelves, static_polys,
            trial_polys, trial_data, trial_format
        )

        trial_fitness = calculate_fitness(trial_data, layout)
        if trial_fitness < best_fitness:
            best_fitness = trial_fitness
            best_polys   = trial_polys
            best_data    = trial_data
            best_format  = trial_format
            print(f"    [LS {ls_iter + 1:02d}] Improved → fitness = {best_fitness:.4f}, bays = {len(best_polys)}")

    return best_polys, best_data, best_format, best_fitness


# ---------------------------------------------------------------------------
# GRASP MAIN LOOP
# ---------------------------------------------------------------------------

def run_grasp_optimization(
    layout:        Layout,
    iterations:    int = 30,
    ls_iterations: int = 15
) -> Tuple[List[Any], float, List[List[Any]]]:
    
    best_layout      = []
    best_fitness     = float('inf')
    best_bays_format = []

    catalog_shelves = [{'id': k, **v} for k, v in layout.bays.items()]
    static_polys    = [layout.esquinas_obstaculo(obs) for obs in layout.obstacles]

    print(f"Starting GRASP: {iterations} iterations, {ls_iterations} LS steps each.")
    print(f"Warehouse area ≈ {_warehouse_area(layout):,.0f} units²\n")

    for i in range(iterations):
        print(f"── Iteration {i + 1:02d}/{iterations} ──────────────────────────")

        # 1. Construction (Pass empty lists to build from scratch)
        placed_polys, shelves_data, bays_format = heuristic_fill(
            layout, catalog_shelves, static_polys, 
            [], [], []
        )
        c_fitness = calculate_fitness(shelves_data, layout)
        print(f"  Construction: {len(placed_polys)} bays placed, fitness = {c_fitness:.4f}")

        # 2. Local search
        placed_polys, shelves_data, bays_format, ls_fitness = local_search(
            placed_polys, shelves_data, bays_format,
            layout, catalog_shelves, static_polys,
            ls_iterations=ls_iterations
        )
        print(f"  After LS    : {len(placed_polys)} bays placed, fitness = {ls_fitness:.4f}")

        # Update global best
        if ls_fitness < best_fitness:
            best_fitness     = ls_fitness
            best_layout      = placed_polys
            best_bays_format = bays_format
            print(f"  *** New global best: {best_fitness:.4f} ***")

    return best_layout, best_fitness, best_bays_format


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ruta_datos = "./PublicTestCases/Case0/"
    try:
        layout_almacen = cargar_datos_logistica(ruta_datos)

        mejor_layout, mejor_score, bays_colocadas = run_grasp_optimization(
            layout_almacen, iterations=10, ls_iterations=5
        )

        nombre_archivo_salida = "layout_optimizado_p00.csv"
        ruta_absoluta = os.path.abspath(nombre_archivo_salida)

        with open(ruta_absoluta, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(bays_colocadas)

        print(f"\n{'='*50}")
        print(f"PROCESS COMPLETE")
        print(f"Output file : {ruta_absoluta}")
        print(f"Best fitness: {mejor_score:.4f}")
        print(f"Bays placed : {len(bays_colocadas)}")
        print(f"{'='*50}")

        visualizar_layout_completo(
            layout_almacen.floor_plan,
            layout_almacen.obstacles,
            layout_almacen.bays,
            layout_almacen.ceiling,
            bays_colocadas
        )

    except FileNotFoundError:
        print(f"Error: data files not found in '{ruta_datos}'")
        print("Please check the path and ensure all CSV files are present.")