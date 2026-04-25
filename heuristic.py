import math
from validator import is_point_in_polygon, calculate_polygons, is_ceiling_valid, check_full_collision

def point_to_segment_dist(px, py, ax, ay, bx, by):
    """Calculates the shortest distance from point P to line segment AB."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    # Project point onto the line
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def get_perimeter_samples(poly, step=10.0):
    """Generates sample points along the perimeter of a polygon."""
    samples = []
    n = len(poly)
    for i in range(n):
        p1, p2 = poly[i], poly[(i+1)%n]
        dist = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
        num_steps = max(1, int(dist / step))
        for j in range(num_steps):
            t = j / num_steps
            samples.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
    return samples

def get_area_samples(poly, step=20.0):
    """Generates sample points inside the area of a polygon."""
    samples = []
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    x = min_x
    while x <= max_x:
        y = min_y
        while y <= max_y:
            if is_point_in_polygon((x, y), poly):
                samples.append((x, y))
            y += step
        x += step
    return samples

def evaluate_placement_score(bay_poly, gap_poly, placed_bays, floor_plan):
    """Scores a placement based on Contact Surface and Gap Superposition."""
    score = 0.0

    # --- 1. Evaluate Bay Adjacency (Contact Surface) ---
    bay_samples = get_perimeter_samples(bay_poly, step=10.0)
    target_segments = []
    
    # Collect wall edges
    for i in range(len(floor_plan)):
        target_segments.append((floor_plan[i], floor_plan[(i+1)%len(floor_plan)]))
    # Collect existing bay edges
    for p in placed_bays:
        p_bay = p['bay']
        for i in range(len(p_bay)):
            target_segments.append((p_bay[i], p_bay[(i+1)%len(p_bay)]))

    contact_hits = 0
    THRESHOLD = 2.0  # Tolerance distance to be considered "touching"
    
    for (sx, sy) in bay_samples:
        for ((ax, ay), (bx, by)) in target_segments:
            if point_to_segment_dist(sx, sy, ax, ay, bx, by) <= THRESHOLD:
                contact_hits += 1
                break # Only count the sample once

    score += contact_hits * 10.0 # Weight for maximizing adjacency

    # --- 2. Evaluate Gap Superposition ---
    gap_samples = get_area_samples(gap_poly, step=20.0)
    overlap_hits = 0
    
    for (gx, gy) in gap_samples:
        for p in placed_bays:
            if is_point_in_polygon((gx, gy), p['gap']):
                overlap_hits += 1
                break

    score += overlap_hits * 15.0 # Higher weight to encourage gap superposition

    return score