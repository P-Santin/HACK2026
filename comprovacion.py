import numpy as np

def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """Algoritme de Ray Casting per saber si un punt està dins d'un polígon girat."""
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def is_ceiling_valid(poly_points: list[tuple[float, float]], bay_h: int, ceiling_map: dict) -> bool:
    """Comprova el sostre punt a punt només dins de l'àrea del polígon."""
    xs = [p[0] for p in poly_points]
    ys = [p[1] for p in poly_points]
    
    min_x, max_x = int(min(xs)), int(max(xs))
    min_y, max_y = int(min(ys)), int(max(ys))

    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            if point_in_polygon(float(x), float(y), poly_points):
                # Busquem l'altura. Si no hi ha dada, assumim que no hi ha sostre (molt alt)
                h_techo = ceiling_map[(float(x), float(y))]
                if bay_h > h_techo:
                    return False
    return True

def polygons_overlap(poly1: list[tuple[float, float]], poly2: list[tuple[float, float]]) -> bool:
    """Detecta col·lisions entre dos polígons qualsevol (SAT)."""
    def get_axes(p):
        axes = []
        for i in range(len(p)):
            p1, p2 = np.array(p[i]), np.array(p[(i + 1) % len(p)])
            edge = p2 - p1
            axes.append(np.array([-edge[1], edge[0]]))
        return axes

    def project(p, axis):
        dots = [np.dot(np.array(pt), axis) for pt in p]
        return min(dots), max(dots)

    axes = get_axes(poly1) + get_axes(poly2)
    for axis in axes:
        norm = np.linalg.norm(axis)
        if norm == 0: continue
        axis = axis / norm
        min1, max1 = project(poly1, axis)
        min2, max2 = project(poly2, axis)
        if max1 <= min2 or max2 <= min1:
            return False
    return True

def calculate_total_poly(p: list[tuple[float, float]], gap: int, costat: str) -> list[tuple[float, float]]:
    """Genera el rectangle expandit que inclou la bahia i el gap."""
    p1, p2 = np.array(p[0]), np.array(p[1])
    p3, p4 = np.array(p[2]), np.array(p[3])
    
    v_width = p2 - p1
    normal = np.array([-v_width[1], v_width[0]])
    norm_val = np.linalg.norm(normal)
    if norm_val == 0: return p # Cas d'error
    normal = normal / norm_val

    if costat == "dreta":
        # Bahia (p1, p2) + Gap cap a la normal
        new_p1, new_p2 = p1, p2
        new_p3 = p2 + normal * gap
        new_p4 = p1 + normal * gap
    else:
        # Gap darrere (p1-normal, p2-normal) + Bahia (p1, p2)
        new_p1 = p1 - normal * gap
        new_p2 = p2 - normal * gap
        new_p3 = p2
        new_p4 = p1
        
    return [tuple(new_p1.tolist()), tuple(new_p2.tolist()), 
            tuple(new_p3.tolist()), tuple(new_p4.tolist())]

def check_full_collision(total_poly: list[tuple[float, float]], obstacles: list[obstacles], placed_bays: list[bays], warehouse: dict[str,float]):
    """Valida límits i col·lisions de l'àrea total (bahia + gap)."""
    # Límits magatzem
    for px, py in total_poly:
        if px < warehouse['min_x'] or px > warehouse['max_x'] or py < warehouse['min_y'] or py > warehouse['max_y']:
            return False

    # Obstacles
    for obs in obstacles:
        if polygons_overlap(total_poly, obs):
            return False

    # Altres bahies (que s'han guardat amb el seu gap)
    for other in placed_bays:
        if polygons_overlap(total_poly, other):
            return False

    return True

def validate_bay_with_double_gap(bay_phys_points: list[tuple[float, float]], bay_h:int, gap_size:int, obstacles:list[obstacles], placed_bays: list[bays], warehouse:list[tuple[float, float]], ceiling_map: dict[tuple[float,float],int]):
    """Funció principal: Sostre -> Gap Dreta? -> Gap Esquerra?"""

    # 2. Provar les dues opcions de Gap
    for costat in ["dreta", "esquerra"]:
        poly_total = calculate_total_poly(bay_phys_points, gap_size, costat)

        if is_ceiling_valid(poly_total,bay_h,ceiling_map) and check_full_collision(poly_total, obstacles, placed_bays, warehouse):
            return True # Retornem el polígon que ha funcionat
            
    return False