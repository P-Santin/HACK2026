import math

def get_ceiling_height(x: float, ceiling_profile: dict) -> float:
    """Busca la altura del techo para una coordenada X dada."""
    xs = ceiling_profile['x']
    hs = ceiling_profile['height']
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i+1]:
            return hs[i]
    return hs[-1] if hs else float('inf')

def is_ceiling_valid(poly_points: list[tuple[float, float]], bay_h: float, ceiling_profile: dict) -> bool:
    """Comprueba si la estantería choca con el techo basado en el perfil 1D de data_collection."""
    xs = [p[0] for p in poly_points]
    min_x, max_x = min(xs), max(xs)
    
    # Comprobar extremos del bounding box
    if bay_h > get_ceiling_height(min_x, ceiling_profile): return False
    if bay_h > get_ceiling_height(max_x, ceiling_profile): return False
    
    # Comprobar si hay un "escalón" del techo que caiga justo en medio de la bahía
    for cx, ch in zip(ceiling_profile['x'], ceiling_profile['height']):
        if min_x < cx < max_x:
            if bay_h > ch:
                return False
    return True

def polygons_overlap(poly1: list[tuple[float, float]], poly2: list[tuple[float, float]]) -> bool:
    """Detecta colisiones usando el Teorema de Ejes Separados (SAT) estándar."""
    def get_axes(p):
        axes = []
        for i in range(len(p)):
            p1, p2 = p[i], p[(i + 1) % len(p)]
            edge = (p2[0] - p1[0], p2[1] - p1[1])
            normal = (-edge[1], edge[0])
            length = math.hypot(*normal)
            if length > 0: axes.append((normal[0]/length, normal[1]/length))
        return axes

    def project(p, axis):
        projs = [(pt[0] * axis[0] + pt[1] * axis[1]) for pt in p]
        return min(projs), max(projs)

    for axis in get_axes(poly1) + get_axes(poly2):
        min1, max1 = project(poly1, axis)
        min2, max2 = project(poly2, axis)
        if max1 < min2 or max2 < min1: # Ajustado a < para permitir tocarse los bordes
            return False
    return True

def calculate_total_poly(p: list[tuple[float, float]], gap: float, costat: str) -> list[tuple[float, float]]:
    """Genera el rectángulo expandido que incluye la bahía y el gap."""
    p1, p2, p3, p4 = p[0], p[1], p[2], p[3]
    
    # Vector director de la profundidad (p1 -> p4)
    v_y = (p4[0] - p1[0], p4[1] - p1[1])
    length = math.hypot(*v_y)
    if length == 0: return p
    
    # Vector normalizado multiplicado por el gap
    gx = (v_y[0] / length) * gap
    gy = (v_y[1] / length) * gap

    if costat == "dreta":
        # Gap hacia "abajo" de p1 y p2 (siguiendo tu lógica de visualización)
        return [(p1[0]-gx, p1[1]-gy), (p2[0]-gx, p2[1]-gy), p3, p4]
    else:
        # Gap hacia "arriba" de p3 y p4
        return [p1, p2, (p3[0]+gx, p3[1]+gy), (p4[0]+gx, p4[1]+gy)]

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