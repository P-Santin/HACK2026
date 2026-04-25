import math
from typing import List, Tuple, Dict, Optional

# Alias para facilitar la lectura de tipos
Polygon = List[Tuple[float, float]]
CeilingProfile = Dict[str, List[float]]

def get_ceiling_height(x: float, ceiling_profile: CeilingProfile) -> float:
    """
    Busca la altura del techo para una coordenada X dada interpolando en el perfil.
    Args:
        x (float): Coordenada X a evaluar.
        ceiling_profile (Dict[str, List[float]]): Diccionario con listas 'x' e 'height'.
    Returns:
        float: La altura del techo en ese punto.
    """
    xs = ceiling_profile['x']
    hs = ceiling_profile['height']
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i+1]:
            return hs[i]
    return hs[-1] if hs else float('inf')

def is_ceiling_valid(poly_points: Polygon, bay_h: float, ceiling_profile: CeilingProfile) -> bool:
    """
    Comprueba si la estantería choca con el techo. Evalúa la estantería y el gap
    Args:
        poly_points (Polygon): Vértices de la estantería.
        bay_h (float): Altura de la estantería.
        ceiling_profile (Dict[str, List[float]]): Perfil del techo.
    Returns:
        bool: True si cabe bajo el techo, False en caso contrario.
    """
    xs = [p[0] for p in poly_points]
    min_x, max_x = min(xs), max(xs)
    
    if bay_h > get_ceiling_height(min_x, ceiling_profile): return False
    if bay_h > get_ceiling_height(max_x, ceiling_profile): return False
    
    for cx, ch in zip(ceiling_profile['x'], ceiling_profile['height']):
        if min_x < cx < max_x and bay_h > ch:
            return False
    return True

def polygons_overlap(poly1: Polygon, poly2: Polygon) -> bool:
    """
    Detecta colisiones entre dos polígonos usando el Teorema de Ejes Separados (SAT).
    Args:
        poly1 (Polygon): Primer polígono.
        poly2 (Polygon): Segundo polígono.
    Returns:
        bool: True si se solapan, False si hay espacio libre entre ellos.
    """
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
        if max1 < min2 or max2 < min1: 
            return False
    return True

def calculate_total_poly(p: Polygon, gap: float, costat: str) -> Polygon:
    """
    Genera el rectángulo expandido que incluye la bahía física y su zona de carga (gap).
    Args:
        p (Polygon): Vértices de la bahía base.
        gap (float): Distancia de la zona de carga.
        costat (str): Dirección del gap ("dreta" o "esquerra").
    Returns:
        Polygon: Los 4 vértices del área total ocupada.
    """
    p1, p2, p3, p4 = p[0], p[1], p[2], p[3]
    v_y = (p4[0] - p1[0], p4[1] - p1[1])
    length = math.hypot(*v_y)
    if length == 0: return p
    
    gx = (v_y[0] / length) * gap
    gy = (v_y[1] / length) * gap

    if costat == "dreta":
        return [(p1[0]-gx, p1[1]-gy), (p2[0]-gx, p2[1]-gy), p3, p4]
    else:
        return [p1, p2, (p3[0]+gx, p3[1]+gy), (p4[0]+gx, p4[1]+gy)]

def check_full_collision(total_poly: Polygon, static_polys: List[Polygon], placed_total_polys: List[Polygon], min_x: float, max_x: float, min_y: float, max_y: float) -> bool:
    """
    Valida límites físicos del almacén y colisiones con otros objetos.
    Args:
        total_poly (Polygon): Polígono extendido (Bahía + Gap).
        static_polys (List[Polygon]): Lista de polígonos de obstáculos fijos.
        placed_total_polys (List[Polygon]): Lista de polígonos de bahías ya colocadas.
        min_x, max_x, min_y, max_y (float): Límites absolutos del almacén.
    Returns:
        bool: True si el polígono es válido (no choca), False si colisiona.
    """
    for px, py in total_poly:
        if px < min_x or px > max_x or py < min_y or py > max_y:
            return False

    for obs in static_polys:
        if polygons_overlap(total_poly, obs): return False

    for other in placed_total_polys:
        if polygons_overlap(total_poly, other): return False

    return True

def validate_bay_with_double_gap(bay_phys_points: Polygon, bay_h: float, gap_size: float, static_polys: List[Polygon], placed_total_polys: List[Polygon], min_x: float, max_x: float, min_y: float, max_y: float, ceiling_profile: CeilingProfile) -> Optional[Polygon]:
    """
    Función validadora maestra. Comprueba el techo y luego busca un gap válido.
    Forzamos siempre 'dreta' porque las rotaciones de 180º ya suplen la 'esquerra',
    manteniendo la sincronización perfecta con el visualizador.
    """
    # 1. Comprobar altura del techo
    if not is_ceiling_valid(bay_phys_points, bay_h, ceiling_profile):
        return None

    # 2. Calcular polígono total con el GAP siempre en su posición por defecto (dreta)
    poly_total = calculate_total_poly(bay_phys_points, gap_size, "dreta")
    
    # 3. Comprobar colisiones
    if check_full_collision(poly_total, static_polys, placed_total_polys, min_x, max_x, min_y, max_y):
        return poly_total 
            
    return None