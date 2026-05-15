import streamlit as st
import re
import io
from opt_engine import parse_orders, generate_excel_bytes, ALL_VEHICLE_IDS, VEHICLE_DISPLAY, DAY_ORDER

st.set_page_config(
    page_title="Optimización de Pedidos",
    page_icon="🍌",
    layout="wide",
)

# ── Estilos ──────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    /* Checkboxes en verde */
    input[type="checkbox"]:checked + div {
        background-color: #2e7d32 !important;
        border-color: #2e7d32 !important;
    }
    [data-testid="stCheckbox"] svg { color: white; }
    [data-baseweb="checkbox"] [data-checked="true"] div {
        background-color: #2e7d32 !important;
        border-color: #2e7d32 !important;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        text-align: center;
    }
    .metric-label { font-size: 13px; color: #666; margin-bottom: 4px; }
    .metric-value { font-size: 26px; font-weight: 600; color: #1a1a1a; }
    div[data-testid="stCheckbox"] label { font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── Encabezado ───────────────────────────────────────────────
col_title, col_logo = st.columns([5, 1])
with col_title:
    st.markdown("## 🍌 Optimización de Pedidos")
    st.markdown("<p style='color:#666; margin-top:-12px;'>Exportadora de Banano — Sistema de rutas</p>", unsafe_allow_html=True)

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

# Extraer número de semana del nombre del archivo
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

# Estado de disponibilidad en session_state (por vehicle_id)
if 'vehicle_availability' not in st.session_state:
    st.session_state.vehicle_availability = {
        vid: {d: True for d in days} for vid in ALL_VEHICLE_IDS
    }

# Sincronizar si los días o vehículos cambian
for vid in ALL_VEHICLE_IDS:
    for d in days:
        if d not in st.session_state.vehicle_availability.get(vid, {}):
            st.session_state.vehicle_availability.setdefault(vid, {})[d] = True

# Tabla de disponibilidad
header_cols = st.columns([2, 2] + [1] * len(days))
header_cols[0].markdown("**Conductor**")
header_cols[1].markdown("<span style='font-size:12px;color:#888'>Vehículo</span>", unsafe_allow_html=True)
for i, d in enumerate(days):
    header_cols[i + 2].markdown(f"<div style='text-align:center;font-weight:600'>{DAY_SHORT.get(d, d)}</div>", unsafe_allow_html=True)

for vid in ALL_VEHICLE_IDS:
    info = VEHICLE_DISPLAY[vid]
    row_cols = st.columns([2, 2] + [1] * len(days))
    row_cols[0].markdown(f"**{info['conductor']}**")
    row_cols[1].markdown(f"<span style='font-size:11px;color:#888'>{info['vehicle']}</span>", unsafe_allow_html=True)
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

col_btn, col_info = st.columns([2, 5])
with col_btn:
    run = st.button("▶  Optimizar semana", type="primary", use_container_width=True)

if run or 'last_result' in st.session_state:
    if run:
        # Construir unavailable_vehicle_ids_by_day
        unavailable_by_day = {}
        for day in days:
            unavail = {vid for vid in ALL_VEHICLE_IDS
                       if not st.session_state.vehicle_availability.get(vid, {}).get(day, True)}
            unavailable_by_day[day] = unavail

        with st.spinner("Calculando rutas óptimas..."):
            excel_bytes, summary = generate_excel_bytes(
                orders, semana_num, unavailable_vehicle_ids_by_day=unavailable_by_day
            )

        if excel_bytes is None:
            st.error("No se encontraron viajes. Revisa los conductores disponibles.")
            st.stop()

        st.session_state.last_result = {
            'excel_bytes':   excel_bytes,
            'summary':       summary,
            'semana_num':    semana_num,
            'filename':      f"RUTAS OPTIMAS SEMANA {semana_num}.xlsx",
        }

    res = st.session_state.last_result
    summary = res['summary']

    # Métricas
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Viajes de exportación", summary['viajes'])
    with m2:
        st.metric("Cajas totales", f"{summary['cajas']:,}".replace(",", "."))
    with m3:
        st.metric("Pallets", int(summary['pallets']))
    with m4:
        st.metric("Costo total", f"${summary['cost']:,.0f}".replace(",", "."))

    st.success("✅ Optimización completada. Descarga el Excel con las rutas.")

    st.download_button(
        label="📥  Descargar Excel de rutas",
        data=res['excel_bytes'],
        file_name=res['filename'],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=False,
    )

st.divider()

# ── Sección 4: Configuración (expandible) ───────────────────
with st.expander("⚙️ Configuración — Precios, fincas y vehículos", expanded=False):
    st.caption("Próximamente podrás editar precios, fincas y capacidades directamente aquí.")

    tab1, tab2, tab3 = st.tabs(["Precios por ruta", "Fincas", "Vehículos"])

    with tab1:
        from opt_engine import VEHICLES_BY_ROUTE
        rows = []
        seen = set()
        for (zone, port), vehicles in VEHICLES_BY_ROUTE.items():
            for v in vehicles:
                key = (v['conductor'], zone, port)
                if key not in seen:
                    seen.add(key)
                    rows.append({
                        'Conductor': v['conductor'],
                        'Zona':      zone,
                        'Puerto':    port,
                        'Tipo':      v['tipo'],
                        'Capacidad': f"{v['capacidad']}P",
                        'Costo':     f"${v['costo']:,}".replace(",", "."),
                    })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        from opt_engine import FARM_ZONES
        farm_rows = [{'Finca': f, 'Zona': z} for f, z in FARM_ZONES.items()]
        st.dataframe(pd.DataFrame(farm_rows), use_container_width=True, hide_index=True)

    with tab3:
        from opt_engine import CONSOLIDACION_ROUTES
        c_rows = []
        for farm, vehicles in CONSOLIDACION_ROUTES.items():
            for v in vehicles:
                c_rows.append({
                    'Finca origen': farm,
                    'Destino':      'DOÑA FRANCIA',
                    'Conductor':    v['conductor'],
                    'Capacidad':    f"{v['capacidad']}P",
                    'Costo':        f"${v['costo']:,}".replace(",", "."),
                })
        st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
