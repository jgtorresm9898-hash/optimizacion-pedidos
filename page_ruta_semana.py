"""
Página: Ruta óptima — Semana.

Misma lógica que "Ruta óptima del día" (daily_optimizer.optimize_day):
se eligen los días de la semana que van a tener despacho, se ingresan los
pallets por finca de CADA uno de esos días (igual que en la página diaria)
y al calcular se muestra el resultado día por día más el consolidado
(suma) de toda la semana. No mueve pallets entre días — cada día se
calcula de forma independiente, igual que en la página diaria.
"""
import pandas as pd
import streamlit as st
from daily_optimizer import optimize_day, ALL_FARMS

FARM_LABELS = {
    'JUANA PIO':     'Juana Pío',
    'DOÑA FRANCIA':  'Doña Francia',
    'SANTA MARIA':   'Santa María',
    'CHISPERO':      'Chispero',
    'SALVAMENTO':    'Salvamento',
    'SAN BARTOLO':   'San Bartolo',
}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]


def money(n):
    return f"${n:,.0f}".replace(",", ".")


def _render_day_result(dia, pallets, resultado):
    st.markdown(f"#### {dia}")
    for t in resultado['trips']:
        fincas_str = " + ".join(
            f"{FARM_LABELS.get(f, f)} {p}P" for f, p in t['farms'].items()
        )
        promedio = t['cost'] / t['total'] if t['total'] else 0
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 4, 2, 2])
            c1.markdown(f"**{t['carrier']}**")
            c2.markdown(f"{fincas_str} — {t['total']}P")
            c3.markdown(f"**{money(t['cost'])}**")
            c4.markdown(f"<span style='color:#888'>{money(promedio)}/P</span>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Pallets del día", f"{sum(pallets.values())}P")
    c2.metric("Costo del día", money(resultado['total_cost']))


def render():
    st.markdown("""
    <style>
        .block-container { padding-top: 2rem; max-width: 900px; }
        div[data-testid="stNumberInput"] label { font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    # ── Encabezado ───────────────────────────────────────────────
    col_title, col_logo = st.columns([3, 2])
    with col_title:
        st.markdown("## 🍌 Ruta óptima — Semana")
        st.markdown("<p style='color:#666; margin-top:-12px;'>Exportadora de Banano</p>",
                    unsafe_allow_html=True)
    with col_logo:
        st.markdown("<div style='text-align:center; padding-top:8px;'>", unsafe_allow_html=True)
        try:
            st.image("LA HACIENDA.jpeg", width=180)
        except Exception:
            pass
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Selección de días con despacho ──────────────────────────
    st.markdown("### ¿Qué días vas a tener despacho esta semana?")
    dias_seleccionados = st.multiselect(
        "Días con pedido", DIAS, label_visibility="collapsed", key='semana_dias_sel',
    )

    if not dias_seleccionados:
        st.info("Selecciona al menos un día para empezar a ingresar los pallets.", icon="📅")
        return

    dias_ordenados = [d for d in DIAS if d in dias_seleccionados]

    st.divider()

    # ── Pallets por finca, uno por cada día elegido ─────────────
    pallets_por_dia = {}
    for dia in dias_ordenados:
        with st.expander(f"📦 Pedido del {dia}", expanded=True):
            st.caption("Escribe los pallets de cada finca. Deja en 0 la finca que no tenga pedido ese día.")
            pallets = {}
            for farm in ALL_FARMS:
                pallets[farm] = st.number_input(
                    FARM_LABELS[farm], min_value=0, step=1, value=0,
                    key=f"semana_pallets_{dia}_{farm}",
                )
            pallets_por_dia[dia] = pallets

    st.divider()

    calcular = st.button("▶  Calcular ruta óptima de la semana", type="primary", use_container_width=True)

    if calcular:
        dias_con_pedido = {d: p for d, p in pallets_por_dia.items() if sum(p.values()) > 0}
        if not dias_con_pedido:
            st.warning("Ingresa al menos una finca con pallets en alguno de los días antes de calcular.")
            st.stop()

        with st.spinner("Calculando la ruta más económica de cada día… con pedidos grandes puede tardar unos segundos."):
            resultados = {d: optimize_day(p) for d, p in dias_con_pedido.items()}

        st.session_state['semana_resultados']   = resultados
        st.session_state['semana_pallets_calc'] = dias_con_pedido

    # ── Resultados (persisten entre reruns hasta el próximo cálculo) ──
    if 'semana_resultados' in st.session_state:
        resultados   = st.session_state['semana_resultados']
        pallets_calc = st.session_state['semana_pallets_calc']

        st.success(f"✅ Ruta óptima calculada para {len(resultados)} día(s)")

        st.markdown("### Desglose por día")
        for dia in dias_ordenados:
            if dia in resultados:
                _render_day_result(dia, pallets_calc[dia], resultados[dia])

        st.divider()

        # ── Consolidado de la semana ─────────────────────────────
        total_pallets = sum(sum(p.values()) for p in pallets_calc.values())
        total_costo   = sum(r['total_cost'] for r in resultados.values())

        st.markdown("### 📊 Consolidado de la semana")
        c1, c2 = st.columns(2)
        c1.metric("Total pallets semana", f"{total_pallets}P")
        c2.metric("Costo total semana", money(total_costo))

        resumen_rows = []
        for dia in dias_ordenados:
            if dia in resultados:
                resumen_rows.append({
                    "Día":     dia,
                    "Pallets": sum(pallets_calc[dia].values()),
                    "Costo":   money(resultados[dia]['total_cost']),
                })
        st.dataframe(pd.DataFrame(resumen_rows), use_container_width=True, hide_index=True)
