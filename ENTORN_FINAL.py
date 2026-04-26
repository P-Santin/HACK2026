import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box
from shapely.affinity import rotate, translate
import numpy as np
from fpdf import FPDF
import datetime
import optimizer
from optimizer import Obstacle, BayType

# --- MOTOR DE LÓGICA ---
class WarehouseEngine:
    def __init__(self, df_w, df_o, df_c, df_b):
        self.floor_poly = Polygon(df_w.values)
        self.obstacles = [box(r.x, r.y, r.x + r.width, r.y + r.depth) for r in df_o.itertuples()]
        df_c = df_c.sort_values(by=0)
        self.ceiling_data = df_c.values.tolist()
        self.bays_catalog = df_b.set_index('id').to_dict(orient='index')

    def get_ceiling_height_at_point(self, x_query):
        current_h = self.ceiling_data[0][1]
        for x_limit, h_val in self.ceiling_data:
            if x_query >= x_limit: current_h = h_val
            else: break
        return current_h

    def get_min_ceiling_in_range(self, x_min, x_max):
        check_points = [x_min, x_max]
        for x_break, h_break in self.ceiling_data:
            if x_min < x_break < x_max: check_points.append(x_break)
        return min([self.get_ceiling_height_at_point(p) for p in check_points])

    def create_bay_geometries(self, b_id, x, y, rot):
        specs = self.bays_catalog[b_id]
        w, d, h, gap = specs['width'], specs['depth'], specs['height'], specs['gap']
        base_rect = box(0, 0, w, d)
        gap_rect = box(0, d, w, d + gap) 
        bay_poly = translate(rotate(base_rect, rot, origin=(0,0)), x, y)
        gap_poly = translate(rotate(gap_rect, rot, origin=(0,0)), x, y)
        return bay_poly, gap_poly, h

    def is_collision(self, poly1, poly2):
        if not poly1.intersects(poly2): return False
        return poly1.intersection(poly2).area > 1e-4

    def validate_bay(self, target_idx, all_bays):
        b = all_bays[target_idx]
        errors = []
        if not self.floor_poly.buffer(1e-4).contains(b['poly']): errors.append("Fuera de muros")
        if not self.floor_poly.buffer(1e-4).contains(b['gap_poly']): errors.append("Gap fuera de muros")
        for obs in self.obstacles:
            if self.is_collision(b['poly'], obs): errors.append("Choca con obstáculo")
            if self.is_collision(b['gap_poly'], obs): errors.append("Gap obstruido")
        min_x, _, max_x, _ = b['poly'].bounds
        if b['h'] > self.get_min_ceiling_in_range(min_x, max_x): errors.append("Excede altura techo")
        for i, other in enumerate(all_bays):
            if i == target_idx: continue
            if self.is_collision(b['poly'], other['poly']): errors.append(f"Solapa con Bay #{i}")
            if self.is_collision(b['poly'], other['gap_poly']): errors.append(f"Pisa Gap de #{i}")
            if self.is_collision(b['gap_poly'], other['poly']): errors.append(f"Gap bloqueado por #{i}")
        return len(errors) == 0, errors




def generate_pdf(placed_bays, engine, metrics):
    pdf = FPDF()
    pdf.add_page()
    
    # --- Encabezado ---
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(52, 152, 219) # Color Azul
    pdf.cell(190, 10, "WAREHOUSE SOLUTION REPORT", ln=True, align="C")
    
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(100)
    fecha = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    pdf.cell(190, 10, f"Fecha de reporte: {fecha}", ln=True, align="C")
    pdf.ln(10)
    
    # --- Caja de Resumen ---
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(0)
    pdf.cell(190, 10, "  Resumen de la Solucion", ln=True, fill=True)
    
    pdf.set_font("Arial", size=11)
    m_list = [
        ("Bays placed:", f"{metrics['num_bays']}"),
        ("Total loads:", f"{metrics['total_loads']}"),
        ("Total price:", f"EUR {metrics['total_price']:,}"),
        ("Price/load:", f"EUR {metrics['price_per_load']:.2f}"),
        ("Area used:", f"{metrics['area_used']:.1f} m2"),
        ("Coverage:", f"{metrics['coverage']:.1f}%")
    ]
    
    for label, val in m_list:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(40, 8, f"  {label}")
        pdf.set_font("Arial", size=10)
        pdf.cell(150, 8, val, ln=True)
    
    # --- Score ---
    pdf.ln(5)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(190, 10, f"SCORE: {metrics['score']:.4f}", ln=True, align="C")
    pdf.ln(10)
    
    # --- Desglose ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "Desglose por Tipo", ln=True)
    
    type_counts = {}
    for b in placed_bays:
        type_counts[b['id']] = type_counts.get(b['id'], 0) + 1
        
    pdf.set_font("Arial", size=10)
    for tid in sorted(type_counts.keys()):
        count = type_counts[tid]
        loads = count * engine.bays_catalog[tid]['n_loads']
        pdf.cell(190, 7, f" - Tipo T{tid}: {count} unidades ({loads} cargas total)", ln=True)
    
    return bytes(pdf.output())




import plotly.graph_objects as go

def create_3d_view(engine, placed_bays):
    fig = go.Figure()

    # 1. Dibujar el Suelo (Warehouse Floor)
    floor_x, floor_y = engine.floor_poly.exterior.xy
    fig.add_trace(go.Scatter3d(
        x=list(floor_x), y=list(floor_y), z=[0]*len(floor_x),
        mode='lines', line=dict(color='black', width=4), name='Muros'
    ))

    # 2. Dibujar Obstáculos (Cajas rojas 3D)
    for obs in engine.obstacles:
        x0, y0, x1, y1 = obs.bounds
        # Creamos un cubo simple para el obstáculo (asumimos altura 2500 o similar)
        h_obs = 2500 
        fig.add_trace(go.Mesh3d(
            x=[x0, x1, x1, x0, x0, x1, x1, x0],
            y=[y0, y0, y1, y1, y0, y0, y1, y1],
            z=[0, 0, 0, 0, h_obs, h_obs, h_obs, h_obs],
            alphahull=0, color='red', opacity=0.3, name='Obstáculo'
        ))

    # 3. Dibujar Bahías colocadas
    safe_colors = ['#3498db', '#1abc9c', '#9b59b6', '#16a085', '#2980b9', '#27ae60']
    for i, b in enumerate(placed_bays):
        x_coords, y_coords = b['poly'].exterior.xy
        z_height = b['h']
        color = safe_colors[int(b['id']) % len(safe_colors)]
        
        # Dibujar el "bloque" de la bahía
        fig.add_trace(go.Mesh3d(
            x=list(x_coords)[:-1] * 2,
            y=list(y_coords)[:-1] * 2,
            z=[0]*4 + [z_height]*4,
            alphahull=0, color=color, opacity=0.8, name=f"Bay #{i}"
        ))

    # Configuración de la cámara y estilo
    fig.update_layout(
        scene=dict(
            xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (Altura)',
            aspectmode='data' # Mantiene las proporciones reales
        ),
        margin=dict(r=0, l=0, b=0, t=0),
        height=600
    )
    return fig




# --- APP STREAMLIT ---
st.set_page_config(layout="wide", page_title="Warehouse Solution Summary")

if 'placed_bays' not in st.session_state: st.session_state.placed_bays = []
if 'edit_x' not in st.session_state: st.session_state.edit_x = 0.0
if 'edit_y' not in st.session_state: st.session_state.edit_y = 0.0
if 'edit_rot' not in st.session_state: st.session_state.edit_rot = 0
if 'edit_id' not in st.session_state: st.session_state.edit_id = 0

with st.sidebar:
    st.header("Carga de Datos")
    
    # 1. OPCIÓN DE CARGA MASIVA (NUEVA)
    st.subheader("Carga Masiva")
    folder_files = st.file_uploader(
        "Suelta aquí los 4 archivos de golpe", 
        type="csv", 
        accept_multiple_files=True,
        help="Deben llamarse: warehouse.csv, obstacles.csv, ceiling.csv y types_of_bays.csv"
    )
    
    # Mapeo automático si se usan varios archivos
    if folder_files:
        f_map = {f.name: f for f in folder_files}
        f_w = f_map.get("warehouse.csv")
        f_o = f_map.get("obstacles.csv")
        f_c = f_map.get("ceiling.csv")
        f_b = f_map.get("types_of_bays.csv") # O 'types_of_bays.csv' según tu archivo
        
        faltantes = [n for n in ["warehouse.csv", "obstacles.csv", "ceiling.csv", "types_of_bays.csv"] if n not in f_map]
        if faltantes:
            st.error(f"Faltan: {', '.join(faltantes)}")
        else:
            st.success("✅ Carpeta detectada correctamente")
    else:
        # 2. CARGA INDIVIDUAL (TU CÓDIGO ORIGINAL)
        st.divider()
        st.subheader("Carga Individual")
        f_w = st.file_uploader("Warehouse CSV", type="csv")
        f_o = st.file_uploader("Obstacles CSV", type="csv")
        f_c = st.file_uploader("Ceiling CSV", type="csv")
        f_b = st.file_uploader("Bays Catalog CSV", type="csv")

    st.divider()
    f_l = st.file_uploader("Importar Layout (Opcional)", type="csv")

if f_w and f_o and f_c and f_b:
    engine = WarehouseEngine(pd.read_csv(f_w, header=None), 
                             pd.read_csv(f_o, header=None, names=['x','y','width','depth']),
                             pd.read_csv(f_c, header=None),
                             pd.read_csv(f_b, header=None, names=['id','width','depth','height','gap','n_loads','price']))

    # Importación Layout
    if f_l and 'layout_loaded' not in st.session_state:
        df_import = pd.read_csv(f_l, header=None)
        for r in df_import.itertuples(index=False):
            b_id = int(r[0])
            if b_id in engine.bays_catalog:
                bp, gp, bh = engine.create_bay_geometries(b_id, r[1], r[2], r[3])
                st.session_state.placed_bays.append({'id': b_id, 'poly': bp, 'gap_poly': gp, 'x': r[1], 'y': r[2], 'rot': r[3], 'h': bh})
        st.session_state.layout_loaded = True
        st.rerun()

    col_map, col_ctrl = st.columns([2, 1.2])

    with col_ctrl:

        # --- EDITOR ---
        st.subheader("🛠️ Editor de Bahía")
        available_ids = list(engine.bays_catalog.keys())
        default_index = available_ids.index(st.session_state.edit_id) if st.session_state.edit_id in available_ids else 0
        sel_id = st.selectbox("Tipo de Bay", options=available_ids, index=default_index)
        c1, c2 = st.columns(2)
        px = c1.number_input("Posición X", value=st.session_state.edit_x, step=50.0)
        py = c2.number_input("Posición Y", value=st.session_state.edit_y, step=50.0)
        rot = st.number_input("Rotación (°)", value=float(st.session_state.edit_rot), min_value=0.0, max_value=359.0, step=1.0)
        
        c_bay, c_gap, h = engine.create_bay_geometries(sel_id, px, py, rot)
        
        if st.button("📥 Colocar / Guardar cambios", use_container_width=True):
            st.session_state.placed_bays.append({'id': sel_id, 'poly': c_bay, 'gap_poly': c_gap, 'x': px, 'y': py, 'rot': rot, 'h': h})
            st.session_state.edit_x, st.session_state.edit_y, st.session_state.edit_rot = 0.0, 0.0, 0
            st.rerun()

        # --- SECCIÓN DEL OPTIMIZADOR ---
        st.divider()
        st.subheader("🤖 Optimización Automática")
        
        tiempo_limit = st.number_input("Límite de tiempo (seg)", value=30, min_value=15)

        if st.button("EJECUTAR ALGORITMO", type="primary", use_container_width=True):
            # Usamos un mensaje vacío para que no bloquee el renderizado
            with st.status("Calculando solución óptima...") as status:
                # 1. Preparar datos
                wh_coords = list(engine.floor_poly.exterior.coords)
                obs_para_alg = [
                    Obstacle(o.bounds[0], o.bounds[1], o.bounds[2]-o.bounds[0], o.bounds[3]-o.bounds[1]) 
                    for o in engine.obstacles
                ]
                bays_para_alg = [
                    BayType(bid, s['width'], s['depth'], s['height'], s['gap'], s['n_loads'], s['price'])
                    for bid, s in engine.bays_catalog.items()
                ]

                # 2. Llamar al optimizador (usando la versión segura)
                solucion = optimizer.run_parallel_optimization(
                    wh_coords, obs_para_alg, engine.ceiling_data, bays_para_alg, float(tiempo_limit)
                )

                # 3. Guardar resultados
                if solucion:
                    st.session_state.placed_bays = []
                    for b in solucion:
                        bp, gp, bh = engine.create_bay_geometries(b.bay_type.id, b.x, b.y, b.rotation)
                        st.session_state.placed_bays.append({
                            'id': b.bay_type.id, 'poly': bp, 'gap_poly': gp, 
                            'x': b.x, 'y': b.y, 'rot': b.rotation, 'h': bh
                        })
                    status.update(label="¡Optimización completa!", state="complete", expanded=False)
                    st.rerun()
                else:
                    status.update(label="No se encontró una solución válida", state="error")

        # --- SECCIÓN DE EXPORTACIÓN ---
        st.divider()
        st.subheader("💾 Exportar Resultados")

        if st.session_state.placed_bays:
            # 1. Convertimos la lista de bahías a un formato de tabla
            data_to_export = []
            for b in st.session_state.placed_bays:
                data_to_export.append({
                    'id': b['id'],
                    'x': round(b['x'], 1),
                    'y': round(b['y'], 1),
                    'rotation': round(b['rot'], 1)
                })
            
            # 2. Creamos un DataFrame de Pandas
            df_export = pd.DataFrame(data_to_export)
            
            # 3. Lo convertimos a CSV (sin índice y sin cabeceras, formato estándar del reto)
            csv_data = df_export.to_csv(index=False, header=False).encode('utf-8')
            
            # 4. Botón de descarga
            st.download_button(
                label="📥 DESCARGAR SOLUCIÓN (CSV)",
                data=csv_data,
                file_name="solution.csv",
                mime="text/csv",
                use_container_width=True,
                help="Descarga las coordenadas de todas las bahías colocadas actualmente."
            )
        else:
            st.info("Coloca algunas bahías para poder exportar la solución.")

        # --- PANEL DE MÉTRICAS ACTUALIZADO ---
        st.divider()
        st.markdown("### 📋 SOLUTION SUMMARY")
        
        total_loads = 0
        total_price = 0
        num_bays = len(st.session_state.placed_bays)

        # 2. Solo entramos a calcular si realmente hay bahías
        if num_bays > 0:
            for b in st.session_state.placed_bays:
                current_id = b['id'] # Usamos un nombre local claro
                
                # Verificamos si el ID existe en el diccionario del catálogo
                if current_id in engine.bays_catalog:
                    total_loads += engine.bays_catalog[current_id]['n_loads']
                    total_price += engine.bays_catalog[current_id]['price']
                else:
                    # Si hay una ID "fantasma", avisamos pero no rompemos el código
                    st.error(f"⚠️ ID {current_id} no encontrada en el catálogo actual.")

        # 3. Cálculos derivados (protegidos contra división por cero)
        price_per_load = total_price / total_loads if total_loads > 0 else 0

        area_used = sum([b['poly'].area for b in st.session_state.placed_bays]) / 1e6 if num_bays > 0 else 0
        usable_area = engine.floor_poly.area / 1e6 if hasattr(engine, 'floor_poly') else 0
        coverage = (area_used / usable_area * 100) if usable_area > 0 else 0

        # 4. Cálculo del Score (tu nueva fórmula)
        coverage_ratio = coverage / 100
        exponent = 2 - coverage_ratio
        score = (price_per_load) ** exponent if total_loads > 0 else 0

        st.code(f"""
Bays placed:    {num_bays}
Total loads:    {total_loads}
Total price:    EUR {total_price:,}
Price/load:     EUR {price_per_load:.1f}
Area used:      {area_used:.1f} m2
Usable area:    {usable_area:.1f} m2
Coverage:       {coverage:.1f}%
Exponent (2-C): {exponent:.4f}
---------------------------------
SCORE:          {score:.4f}
(lower = better)
        """, language="text")

        # 3. Empaquetar métricas para el PDF (Asegúrate de que 'coverage' existe aquí)
        current_metrics = {
            'num_bays': num_bays,
            'total_loads': total_loads,
            'total_price': total_price,
            'price_per_load': price_per_load,
            'area_used': area_used,
            'coverage': coverage,  # <--- Esto es lo que causaba el error
            'score': score
        }

        # 2. Generar y botón de descarga
        try:
            # Generamos el PDF
            pdf_result = generate_pdf(st.session_state.placed_bays, engine, current_metrics)
            
            # Convertimos a bytes explícitamente por si acaso
            pdf_bytes = bytes(pdf_result)
            
            st.download_button(
                label="📥 Descargar Reporte PDF",
                data=pdf_bytes,
                file_name=f"reporte_almacen_{datetime.datetime.now().strftime('%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Error al generar PDF: {e}")

        # Type Breakdown
        st.markdown("**TYPE BREAKDOWN**")
        type_counts = {}
        for b in st.session_state.placed_bays:
            tid = b['id']
            type_counts[tid] = type_counts.get(tid, 0) + 1
        
        for tid in sorted(type_counts.keys()):
            count = type_counts[tid]
            loads_of_type = count * engine.bays_catalog[tid]['n_loads']
            st.write(f"• **T{tid}:** x{count} -> {loads_of_type} loads")

        st.divider()
        if st.button("Vaciar Almacén"):
            st.session_state.placed_bays = []
            if 'layout_loaded' in st.session_state: del st.session_state.layout_loaded
            st.rerun()

        # Lista para editar/borrar
        for i in range(len(st.session_state.placed_bays)):
            is_ok, errs = engine.validate_bay(i, st.session_state.placed_bays)
            with st.expander(f"{'✅' if is_ok else '⚠️'} Bay #{i} (ID:{st.session_state.placed_bays[i]['id']})"):
                ce1, ce2 = st.columns(2)
                if ce1.button("📝 Editar", key=f"ed_{i}"):
                    b_edit = st.session_state.placed_bays.pop(i)
                    st.session_state.edit_x, st.session_state.edit_y = b_edit['x'], b_edit['y']
                    st.session_state.edit_rot, st.session_state.edit_id = b_edit['rot'], b_edit['id']
                    st.rerun()
                if ce2.button("🗑️ Borrar", key=f"del_{i}"):
                    st.session_state.placed_bays.pop(i); st.rerun()
                if not is_ok:
                    for e in errs: st.write(f":orange[• {e}]")

    with col_map:

        tab2d, tab3d = st.tabs(["Plano 2D", "Vista 3D Interactiva"])

        with tab2d:
            fig, ax = plt.subplots(figsize=(10, 10))
            # Dibujar Warehouse y Obstáculos
            ax.plot(*engine.floor_poly.exterior.xy, color='black', lw=2)
            for obs in engine.obstacles: 
                ax.fill(*obs.exterior.xy, color='#ff4b4b', alpha=0.2, hatch='//')
            
            # Paleta de colores estéticos (No rojos/naranjas)
            # Azul, Esmeralda, Violeta, Turquesa, Índigo, Menta
            safe_colors = ['#3498db', '#1abc9c', '#9b59b6', '#16a085', '#2980b9', '#27ae60']

            for i, b in enumerate(st.session_state.placed_bays):
                is_ok, _ = engine.validate_bay(i, st.session_state.placed_bays)
                
                # LÓGICA DE COLOR DINÁMICA:
                # Si está OK -> Color según su Tipo
                # Si está MAL -> Naranja sólido
                if is_ok:
                    base_color = safe_colors[int(b['id']) % len(safe_colors)]
                    edge_color = 'white'
                    line_width = 1
                else:
                    base_color = '#e67e22' # Naranja de error
                    edge_color = '#d35400' # Naranja más oscuro para el borde
                    line_width = 2
                
                # Dibujar Estructura (Relleno completo)
                ax.fill(*b['poly'].exterior.xy, color=base_color, alpha=0.8, edgecolor=edge_color, lw=line_width)
                
                # Dibujar Gap (Sutil)
                ax.fill(*b['gap_poly'].exterior.xy, color=base_color, alpha=0.2, ls=':')

                # --- POSICIONAMIENTO DE TEXTO INTERNO ---
                cx, cy = b['poly'].centroid.x, b['poly'].centroid.y
                minx, miny, maxx, maxy = b['poly'].bounds
                offset = (maxy - miny) * 0.15

                # ETIQUETA DE TIPO (T{id})
                ax.text(cx, cy + offset, f"T{b['id']}", 
                        color='white', fontsize=8, fontweight='bold', ha='center', va='center',
                        bbox=dict(facecolor='black', alpha=0.1, edgecolor='none', boxstyle='round,pad=0.1'))

                # NÚMERO DE ÍNDICE
                ax.text(cx, cy - offset, str(i), 
                        color='white', fontsize=10, fontweight='bold', ha='center', va='center',
                        bbox=dict(facecolor='black', alpha=0.2, edgecolor='none', boxstyle='round,pad=0.2'))
        
            # Preview de la bay que estás moviendo (Azul vibrante)
            ax.plot(*c_bay.exterior.xy, color='#0000FF', lw=2, ls='--')
            ax.fill(*c_bay.exterior.xy, color='#0000FF', alpha=0.1)
            
            ax.set_aspect('equal')
            plt.grid(True, alpha=0.1, ls='--')
            st.pyplot(fig)
        
        with tab3d:
            st.subheader("Inspección Volumétrica")
            if st.session_state.placed_bays:
                fig_3d = create_3d_view(engine, st.session_state.placed_bays)
                st.plotly_chart(fig_3d, use_container_width=True)
            else:
                st.info("Coloca algunas bahías para ver la reconstrucción 3D.")
else:
    st.info("Carga los CSV para habilitar el panel de métricas y el editor.")
