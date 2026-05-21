import streamlit as st
import re
import io
import pandas as pd
from opt_engine import (
    parse_orders, generate_excel_bytes,
    ALL_VEHICLE_IDS, VEHICLE_DISPLAY, DAY_ORDER,
)
import opt_engine as _oe

st.set_page_config(
    page_title="Optimización de Pedidos",
    page_icon="🍌",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    [data-baseweb="checkbox"] [data-checked="true"] div {
        background-color: #2e7d32 !important;
        border-color: #2e7d32 !important;
    }
    div[data-testid="stCheckbox"] label { font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── Encabezado ───────────────────────────────────────────────
col_title, col_logo = st.columns([3, 2])
with col_title:
    st.markdown("## 🍌 Optimización de Pedidos")
    st.markdown("<p style='color:#666; margin-top:-12px;'>Exportadora de Banano — Sistema de rutas</p>",
                unsafe_allow_html=True)
with col_logo:
    st.markdown("<div style='text-align:center; padding-top:8px;'>", unsafe_allow_html=True)
    st.image("LA HACIENDA.jpeg", width=220)
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ── Sección 1: Cargar archivo ────────────────────────────────
st.markdown("### 📂 Pedido semanal")
uploaded = st.file_uploader(
    "Arrastra el archivo Excel o haz clic para seleccionarlo",
    type=["xlsx"],
    label_visibility="collapsed",
)

if not uploaded:
    st.info("Sube el archivo **PEDIDO SEMANA XX.xlsx** para comenzar.", icon="📄")
    st.stop()

semana_match = re.search(r'(\d+)', uploaded.name)
semana_num   = semana_match.group(1) if semana_match else '?'

try:
    file_bytes = uploaded.read()
    orders     = parse_orders(io.BytesIO(file_bytes))
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

days = sorted(orders.keys(), key=lambda d: DAY_ORDER.index(d) if d in DAY_ORDER else 99)
st.success(f"✅ **{uploaded.name}** cargado — Semana {semana_num} — Días: {', '.join(d.capitalize() for d in days)}")

st.divider()

# ── Sección 2: Vehículos disponibles ────────────────────────
st.markdown("### 🚛 Vehículos disponibles")
st.caption("Desmarca los días en que el vehículo NO estará disponible")

DAY_SHORT = {'LUNES': 'Lun', 'MARTES': 'Mar', 'MIERCOLES': 'Mié', 'MIÉRCOLES': 'Mié',
             'JUEVES': 'Jue', 'VIERNES': 'Vie', 'SABADO': 'Sáb', 'SÁBADO': 'Sáb'}

if 'vehicle_availability' not in st.session_state:
    st.session_state.vehicle_availability = {
        vid: {d: True for d in days} for vid in ALL_VEHICLE_IDS
    }
for vid in ALL_VEHICLE_IDS:
    for d in days:
        if d not in st.session_state.vehicle_availability.get(vid, {}):
            st.session_state.vehicle_availability.setdefault(vid, {})[d] = True

header_cols = st.columns([2, 2] + [1] * len(days))
header_cols[0].markdown("**Conductor**")
header_cols[1].markdown("<span style='font-size:12px;color:#888'>Vehículo</span>", unsafe_allow_html=True)
for i, d in enumerate(days):
    header_cols[i + 2].markdown(
        f"<div style='text-align:center;font-weight:600'>{DAY_SHORT.get(d, d)}</div>",
        unsafe_allow_html=True,
    )

for vid in ALL_VEHICLE_IDS:
    info     = _oe.VEHICLE_DISPLAY[vid]
    row_cols = st.columns([2, 2] + [1] * len(days))
    row_cols[0].markdown(f"**{info['conductor']}**")
    row_cols[1].markdown(f"<span style='font-size:11px;color:#888'>{info['vehicle']}</span>",
                         unsafe_allow_html=True)
    for i, day in enumerate(days):
        key = f"avail_{vid}_{day}"
        val = row_cols[i + 2].checkbox(
            label=" ",
            value=st.session_state.vehicle_availability[vid].get(day, True),
            key=key,
            label_visibility="collapsed",
        )
        st.session_state.vehicle_availability[vid][day] = val

st.divider()

# ── Sección 3: Optimizar ─────────────────────────────────────
st.markdown("### ⚙️ Optimización")

col_btn, _ = st.columns([2, 5])
with col_btn:
    run = st.button("▶  Optimizar semana", type="primary", use_container_width=True)

if run or 'last_result' in st.session_state:
    if run:
        unavailable_by_day = {}
        for day in days:
            unavail = {vid for vid in ALL_VEHICLE_IDS
                       if not st.session_state.vehicle_availability.get(vid, {}).get(day, True)}
            unavailable_by_day[day] = unavail

        with st.spinner("Calculando rutas óptimas..."):
            excel_bytes, summary = generate_excel_bytes(
                orders, semana_num,
                unavailable_vehicle_ids_by_day=unavailable_by_day,
            )

        if excel_bytes is None:
            st.error("No se encontraron viajes. Revisa los conductores disponibles.")
            st.stop()

        st.session_state.last_result = {
            'excel_bytes': excel_bytes,
            'summary':     summary,
            'semana_num':  semana_num,
            'filename':    f"RUTAS OPTIMAS SEMANA {semana_num}.xlsx",
        }

    res     = st.session_state.last_result
    summary = res['summary']

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Viajes de exportación", summary['viajes'])
    m2.metric("Cajas totales",         f"{summary['cajas']:,}".replace(",", "."))
    m3.metric("Pallets",               int(summary['pallets']))
    m4.metric("Costo total",           f"${summary['cost']:,.0f}".replace(",", "."))

    st.success("✅ Optimización completada. Descarga el Excel con las rutas.")
    st.download_button(
        label="📥  Descargar Excel de rutas",
        data=res['excel_bytes'],
        file_name=res['filename'],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

st.divider()

# ── Sección 4: Configuración ─────────────────────────────────
with st.expander("⚙️ Configuración — Precios, fincas y vehículos", expanded=False):
    tab1, tab2, tab3 = st.tabs(["Precios por ruta", "Fincas", "Vehículos"])

    # ── Tab 1: VEHICLES_BY_ROUTE ─────────────────────────────
    with tab1:
        st.caption("Edita el costo de cualquier ruta. Presiona **Guardar precios** para aplicar en la próxima optimización.")

        price_rows = []
        seen_p = set()
        for (zone, port), vehicles in _oe.VEHICLES_BY_ROUTE.items():
            for v in vehicles:
                pk = (v['conductor'], zone, port, v['tipo'])
                if pk not in seen_p:
                    seen_p.add(pk)
                    price_rows.append({
                        'Conductor': v['conductor'],
                        'Zona':      zone,
                        'Puerto':    port,
                        'Tipo':      v['tipo'],
                        'Capacidad': v['capacidad'],
                        'Costo':     v['costo'],
                    })

        edited_prices = st.data_editor(
            pd.DataFrame(price_rows),
            column_config={
                'Conductor': st.column_config.TextColumn(disabled=True),
                'Zona':      st.column_config.TextColumn(disabled=True),
                'Puerto':    st.column_config.TextColumn(disabled=True),
                'Tipo':      st.column_config.TextColumn(disabled=True),
                'Capacidad': st.column_config.NumberColumn("Cap. (P)", disabled=True),
                'Costo':     st.column_config.NumberColumn("Costo ($)", min_value=0,
                                                           step=50000, format="$%d"),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key='price_editor',
        )

        if st.button("💾 Guardar precios", key='save_prices', type='primary'):
            n = 0
            for _, row in edited_prices.iterrows():
                rk = (row['Zona'], row['Puerto'])
                for v in _oe.VEHICLES_BY_ROUTE.get(rk, []):
                    if v['conductor'] == row['Conductor'] and v['tipo'] == row['Tipo']:
                        if v['costo'] != int(row['Costo']):
                            v['costo'] = int(row['Costo'])
                            n += 1
            st.success(f"✅ {n} precio(s) actualizado(s)." if n else "Sin cambios.")

    # ── Tab 2: FARM_ZONES ────────────────────────────────────
    with tab2:
        st.caption("Cambia la zona de origen de cada finca (CHIGORODO o APARTADO).")

        edited_farms = st.data_editor(
            pd.DataFrame([{'Finca': f, 'Zona': z} for f, z in _oe.FARM_ZONES.items()]),
            column_config={
                'Finca': st.column_config.TextColumn(disabled=True),
                'Zona':  st.column_config.SelectboxColumn(
                    options=["CHIGORODO", "APARTADO"], required=True
                ),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key='farm_editor',
        )

        if st.button("💾 Guardar fincas", key='save_farms', type='primary'):
            n = 0
            for _, row in edited_farms.iterrows():
                if _oe.FARM_ZONES.get(row['Finca']) != row['Zona']:
                    _oe.FARM_ZONES[row['Finca']] = row['Zona']
                    n += 1
            st.success(f"✅ {n} finca(s) actualizada(s)." if n else "Sin cambios.")

    # ── Tab 3: CONSOLIDACION_ROUTES + flota ──────────────────
    with tab3:
        st.caption("Edita el costo y capacidad de los viajes de consolidación (Merbin). "
                   "La flota principal se muestra abajo como referencia.")

        # Editable: CONSOLIDACION_ROUTES
        c_rows = []
        for farm, vehicles in _oe.CONSOLIDACION_ROUTES.items():
            for v in vehicles:
                c_rows.append({
                    'Finca origen': farm,
                    'Conductor':    v['conductor'],
                    'Capacidad':    v['capacidad'],
                    'Costo':        v['costo'],
                })

        edited_consol = st.data_editor(
            pd.DataFrame(c_rows),
            column_config={
                'Finca origen': st.column_config.TextColumn(disabled=True),
                'Conductor':    st.column_config.TextColumn(disabled=True),
                'Capacidad':    st.column_config.NumberColumn("Cap. (P)", min_value=1, step=1),
                'Costo':        st.column_config.NumberColumn("Costo ($)", min_value=0,
                                                              step=10000, format="$%d"),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key='consol_editor',
        )

        if st.button("💾 Guardar consolidaciones", key='save_consol', type='primary'):
            n = 0
            for _, row in edited_consol.iterrows():
                farm = row['Finca origen']
                for v in _oe.CONSOLIDACION_ROUTES.get(farm, []):
                    changed = False
                    if v['capacidad'] != int(row['Capacidad']):
                        v['capacidad'] = int(row['Capacidad']); changed = True
                    if v['costo'] != int(row['Costo']):
                        v['costo'] = int(row['Costo']); changed = True
                    if changed:
                        n += 1
            st.success(f"✅ {n} entrada(s) actualizada(s)." if n else "Sin cambios.")

        st.divider()
        st.caption("**Flota principal** (referencia — edita los precios en la pestaña 'Precios por ruta')")
        v_rows = []
        for vid, info in _oe.VEHICLE_DISPLAY.items():
            rutas = []
            for (zone, port), vehicles in _oe.VEHICLES_BY_ROUTE.items():
                for v in vehicles:
                    if v.get('vehicle_id') == vid:
                        rutas.append(f"{zone} → {port}")
            for farm, vehicles in _oe.CONSOLIDACION_ROUTES.items():
                for v in vehicles:
                    if v.get('vehicle_id') == vid:
                        rutas.append(f"Consol: {farm}")
            v_rows.append({
                'Conductor': info['conductor'],
                'Vehículo':  info['vehicle'],
                'Rutas':     ' | '.join(rutas) if rutas else '—',
            })
        st.dataframe(pd.DataFrame(v_rows), use_container_width=True, hide_index=True)
