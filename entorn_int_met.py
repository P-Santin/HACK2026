import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box
from shapely.affinity import rotate, translate
import numpy as np

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

# --- APP STREAMLIT ---
st.set_page_config(layout="wide", page_title="Warehouse Solution Summary")

if 'placed_bays' not in st.session_state: st.session_state.placed_bays = []
if 'edit_x' not in st.session_state: st.session_state.edit_x = 0.0
if 'edit_y' not in st.session_state: st.session_state.edit_y = 0.0
if 'edit_rot' not in st.session_state: st.session_state.edit_rot = 0
if 'edit_id' not in st.session_state: st.session_state.edit_id = 0

with st.sidebar:
    st.header("Carga de Datos")
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
        rot = st.number_input("Rotación (°)", value=st.session_state.edit_rot, min_value=0, max_value=359)
        
        c_bay, c_gap, h = engine.create_bay_geometries(sel_id, px, py, rot)
        
        if st.button("📥 Colocar / Guardar cambios", use_container_width=True):
            st.session_state.placed_bays.append({'id': sel_id, 'poly': c_bay, 'gap_poly': c_gap, 'x': px, 'y': py, 'rot': rot, 'h': h})
            st.session_state.edit_x, st.session_state.edit_y, st.session_state.edit_rot = 0.0, 0.0, 0
            st.rerun()

        # --- PANEL DE MÉTRICAS (BASADO EN TU IMAGEN) ---
        st.divider()
        st.markdown("### 📋 SOLUTION SUMMARY")
        
        # Cálculos base
        num_bays = len(st.session_state.placed_bays)
        total_loads = sum([engine.bays_catalog[b['id']]['n_loads'] for b in st.session_state.placed_bays])
        total_price = sum([engine.bays_catalog[b['id']]['price'] for b in st.session_state.placed_bays])
        price_per_load = total_price / total_loads if total_loads > 0 else 0
        
        area_used = sum([b['poly'].area for b in st.session_state.placed_bays]) / 1e6 # Pasar a m2 (asumiendo mm)
        usable_area = engine.floor_poly.area / 1e6
        coverage = (area_used / usable_area * 100) if usable_area > 0 else 0
        
        # Simulación de Score y Exponent (Ajustar según vuestra fórmula real)
        exponent = 1.403 # Valor fijo ejemplo
        score = total_price / (total_loads**exponent) if total_loads > 0 else 0

        # Formato estilo tabla de la imagen
        st.code(f"""
Bays placed:    {num_bays}
Total loads:    {total_loads}
Total price:    EUR {total_price:,}
Price/load:     EUR {price_per_load:.1f}
Area used:      {area_used:.1f} m2
Usable area:    {usable_area:.1f} m2
Coverage:       {coverage:.1f}%
Exponent:       {exponent}
---------------------------------
SCORE:          {score:.4f}
(lower = better)
        """, language="text")

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
else:
    st.info("Carga los CSV para habilitar el panel de métricas y el editor.")
