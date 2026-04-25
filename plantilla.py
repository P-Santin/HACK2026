import numpy as np
import random
import math

class Estanteria:
    def __init__(self, id_tipo, ancho, largo, alto, coste, carga, zona_carga_profundidad):
        self.id_tipo = id_tipo
        self.ancho = ancho
        self.largo = largo
        self.alto = alto
        self.coste = coste
        self.carga = carga
        self.zona_carga_profundidad = zona_carga_profundidad
        # Area física de la estantería (sin la zona de carga)
        self.area = ancho * largo

class AlmacenGrid:
    def __init__(self, ancho_grid, largo_grid, altura_maxima):
        self.ancho = ancho_grid
        self.largo = largo_grid
        
        # Grid principal: 0 = libre, 1 = ocupado por estantería, 2 = obstáculo, 3 = zona de carga
        self.grid = np.zeros((self.ancho, self.largo), dtype=int)
        
        # Grid de alturas máximas permitidas en cada celda
        self.grid_alturas = np.full((self.ancho, self.largo), altura_maxima, dtype=int)
        
        self.estanterias_colocadas = []

    def anadir_obstaculo(self, x, y, ancho, largo):
        """Marca una zona como obstáculo insalvable."""
        if (x + ancho > self.ancho or y + largo > self.largo or 
            x < 0 or y < 0):
            return False
        self.grid[x:x+ancho, y:y+largo] = 2
        self.grid_alturas[x:x+ancho, y:y+largo] = 0
        return True

    def puede_colocar(self, estanteria, x, y, orientacion_carga):
        """
        Verifica si la estantería Y su zona de carga caben en la posición dada.
        orientacion_carga: 'N', 'S', 'E', 'O' indica hacia dónde mira la zona de carga.
        """
        w, l = estanteria.ancho, estanteria.largo
        
        # 1. Comprobar límites físicos de la estantería
        if x < 0 or y < 0 or x + w > self.ancho or y + l > self.largo:
            return False
            
        # 2. Comprobar colisiones y restricciones de altura
        espacio_fisico = self.grid[x:x+w, y:y+l]
        alturas_disponibles = self.grid_alturas[x:x+w, y:y+l]
        
        # No puede haber obstáculos (2) ni otras estanterías (1)
        if np.any(espacio_fisico >= 1):
            return False
        # La altura debe ser suficiente
        if np.any(alturas_disponibles < estanteria.alto):
            return False

        # 3. Calcular y comprobar la zona de carga
        zc_prof = estanteria.zona_carga_profundidad
        zx, zy, zw, zl = x, y, w, l
        
        if orientacion_carga == 'N':
            zy = y - zc_prof; zl = zc_prof
        elif orientacion_carga == 'S':
            zy = y + l; zl = zc_prof
        elif orientacion_carga == 'E':
            zx = x + w; zw = zc_prof
        elif orientacion_carga == 'O':
            zx = x - zc_prof; zw = zc_prof
        else:
            return False

        # Comprobar límites de la zona de carga
        if zx < 0 or zy < 0 or zx + zw > self.ancho or zy + zl > self.largo:
            return False
            
        # La zona de carga no puede colisionar con estanterías (1) ni obstáculos (2)
        # Pero puede colisionar con otras zonas de carga (3)
        espacio_carga = self.grid[zx:zx+zw, zy:zy+zl]
        if np.any(espacio_carga == 1) or np.any(espacio_carga == 2):
            return False
            
        return True

    def colocar_estanteria(self, estanteria, x, y, orientacion_carga):
        """Coloca la estantería y marca su zona de carga. Retorna True si fue exitoso."""
        if not self.puede_colocar(estanteria, x, y, orientacion_carga):
            return False
            
        w, l = estanteria.ancho, estanteria.largo
        
        # Marcar estantería
        self.grid[x:x+w, y:y+l] = 1
        
        # Marcar zona de carga
        zc_prof = estanteria.zona_carga_profundidad
        zx, zy, zw, zl = x, y, w, l
        
        if orientacion_carga == 'N':
            zy = y - zc_prof; zl = zc_prof
        elif orientacion_carga == 'S':
            zy = y + l; zl = zc_prof
        elif orientacion_carga == 'E':
            zx = x + w; zw = zc_prof
        elif orientacion_carga == 'O':
            zx = x - zc_prof; zw = zc_prof
            
        # Marcar zona de carga (3) solo si no hay estanterías u obstáculos
        zona_carga = self.grid[zx:zx+zw, zy:zy+zl]
        zona_carga[zona_carga == 0] = 3  # Solo marcar celdas libres
        
        self.estanterias_colocadas.append(estanteria)
        return True

    def calcular_coste_objetivo(self):
        """Aplica la fórmula: ((sum_prices)/(sum_loads))^(2 - PercentageAreaUsed)"""
        if not self.estanterias_colocadas:
            return float('inf')
            
        sum_prices = sum(e.coste for e in self.estanterias_colocadas)
        sum_loads = sum(e.carga for e in self.estanterias_colocadas)
        
        area_ocupada = sum(e.area for e in self.estanterias_colocadas)
        area_total_valida = np.count_nonzero(self.grid != 2)  # Total menos obstáculos
        
        if area_total_valida == 0 or sum_loads == 0:
            return float('inf')
            
        percentage_area_used = area_ocupada / area_total_valida
        
        base = sum_prices / sum_loads
        exponente = 2.0 - percentage_area_used
        
        return math.pow(base, exponente)

    def visualizar(self):
        """Método auxiliar para visualizar el estado del almacén"""
        simbolos = {
            0: '.',  # Libre
            1: 'E',  # Estantería
            2: '#',  # Obstáculo
            3: 'Z'   # Zona de carga
        }
        for y in range(self.largo):
            for x in range(self.ancho):
                print(simbolos[self.grid[x, y]], end=' ')
            print()
        print()

def optimizar_almacen_heuristic(tipos_estanterias, iteraciones=1000, 
                                ancho_almacen=50, largo_almacen=50, 
                                altura_max=30):
    """
    Constructor aleatorio mejorado con estrategia greedy.
    """
    mejor_almacen = None
    mejor_coste = float('inf')
    
    for iteracion in range(iteraciones):
        # 1. Inicializar almacén
        almacen = AlmacenGrid(ancho_almacen, largo_almacen, altura_max)
        
        # Añadir obstáculos de ejemplo
        # almacen.anadir_obstaculo(20, 20, 5, 5)
        
        # 2. Colocar estanterías aleatoriamente
        intentos_totales = 0
        max_intentos = ancho_almacen * largo_almacen  # Límite basado en el espacio
        
        while intentos_totales < max_intentos:
            # Seleccionar tipo de estantería al azar
            tipo_est = random.choice(tipos_estanterias)
            
            # Generar posición y orientación al azar
            rx = random.randint(0, almacen.ancho - tipo_est.ancho)
            ry = random.randint(0, almacen.largo - tipo_est.largo)
            orientacion = random.choice(['N', 'S', 'E', 'O'])
            
            if almacen.colocar_estanteria(tipo_est, rx, ry, orientacion):
                intentos_totales = 0  # Reiniciar al tener éxito
            else:
                intentos_totales += 1
        
        # Evaluar diseño generado
        coste_actual = almacen.calcular_coste_objetivo()
        if coste_actual < mejor_coste:
            mejor_coste = coste_actual
            mejor_almacen = almacen
            print(f"Iteración {iteracion}: Nuevo mejor coste = {coste_actual:.4f}")
    
    return mejor_almacen, mejor_coste

# Ejemplo de uso con diferentes estrategias:
def optimizar_almacen_genetico(tipos_estanterias, poblacion=50, generaciones=100):
    """
    Esqueleto para implementar un algoritmo genético más avanzado.
    Esta es una versión simplificada que deberías expandir.
    """
    # Aquí implementarías:
    # 1. Codificación del cromosoma (lista de (tipo, x, y, orientación))
    # 2. Operadores de cruce y mutación
    # 3. Selección por torneo o ruleta
    # 4. Elitismo
    
    # Por ahora retornamos la versión heurística
    return optimizar_almacen_heuristic(tipos_estanterias, iteraciones=1000)

if __name__ == '__main__':
    # Definir catálogo de estanterías más diverso
    catalogo = [
        Estanteria(1, 4, 2, 20, 1000, 5000, 3),
        Estanteria(2, 6, 2, 25, 1400, 8000, 4),
        Estanteria(3, 3, 3, 15, 800,  3000, 3),
        Estanteria(4, 5, 4, 22, 1200, 6500, 5),
        Estanteria(5, 2, 2, 12, 500,  2000, 2)
    ]
    
    print("Iniciando optimización...")
    mejor_layout, coste_final = optimizar_almacen_heuristic(
        catalogo, 
        iteraciones=2000,
        ancho_almacen=40,
        largo_almacen=40,
        altura_max=30
    )
    
    print("\n=== RESULTADOS DE LA OPTIMIZACIÓN ===")
    print(f"Mejor coste obtenido: {coste_final:.4f}")
    print(f"Total estanterías ubicadas: {len(mejor_layout.estanterias_colocadas)}")
    
    # Estadísticas detalladas
    sum_prices = sum(e.coste for e in mejor_layout.estanterias_colocadas)
    sum_loads = sum(e.carga for e in mejor_layout.estanterias_colocadas)
    area_ocupada = sum(e.area for e in mejor_layout.estanterias_colocadas)
    area_total = np.count_nonzero(mejor_layout.grid != 2)
    area_carga = np.count_nonzero(mejor_layout.grid == 3)
    
    print(f"Suma de precios: {sum_prices}")
    print(f"Suma de cargas: {sum_loads}")
    print(f"Relación precio/carga: {sum_prices/sum_loads:.4f}")
    print(f"Área ocupada por estanterías: {area_ocupada} u²")
    print(f"Área total disponible: {area_total} u²")
    print(f"Área zonas de carga: {area_carga} u²")
    print(f"Porcentaje de área utilizada: {(area_ocupada/area_total)*100:.2f}%")
    
    # Mostrar distribución de tipos
    tipos_contados = {}
    for est in mejor_layout.estanterias_colocadas:
        tipos_contados[est.id_tipo] = tipos_contados.get(est.id_tipo, 0) + 1
    
    print("\nDistribución de estanterías:")
    for tipo_id, cantidad in sorted(tipos_contados.items()):
        print(f"  Tipo {tipo_id}: {cantidad} unidades")
    
    print("\nMapa del almacén (primeros 10x10):")
    mejor_layout.visualizar()