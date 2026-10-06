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
from daily_optimizer import optimize_day, ALL_FARMS, CARRIERS, CARRIER_LABELS

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


def _conductor_toggles(key_prefix):
    """Fila de botones para marcar cada conductor disponible/no disponible
    (p.ej. carro varado). Aplica a todos los días que se calculen. Devuelve
    el set de conductores NO disponibles."""
    cols = st.columns(len(CARRIERS))
    disponibilidad = {}
    for i, c in enumerate(CARRIERS):
        skey = f"{key_prefix}_disp_{c}"
        if skey not in st.session_state:
            st.session_state[skey] = True
        disponible = st.session_state[skey]
        label = f"✅ {CARRIER_LABELS[c]}" if disponible else f"🚫 {CARRIER_LABELS[c]} (no disp.)"
        if cols[i].button(label, key=f"{key_prefix}_btn_{c}", use_container_width=True,
                           type="secondary" if disponible else "primary"):
            st.session_state[skey] = not disponible
            st.rerun()
        disponibilidad[c] = st.session_state[skey]
    return {c for c, ok in disponibilidad.items() if not ok}


def _render_day_result(dia, pallets, resultado):
    st.markdown(f"#### {dia}")
    for nota in resultado.get('notas', []):
        st.info(nota, icon="ℹ️")
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

    st.markdown("### Conductores disponibles esta semana")
    st.caption("Si alguno tiene el carro varado o no va a trabajar, quítalo aquí — aplica a todos los días que calcules.")
    unavailable = _conductor_toggles("semana_dia")

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
            try:
                resultados = {d: optimize_day(p, unavailable_carriers=unavailable) for d, p in dias_con_pedido.items()}
                resultados_e2 = {d: optimize_day(p, unavailable_carriers=unavailable, forzar_trailer_dos_viajes=True)
                                 for d, p in dias_con_pedido.items()}
            except RuntimeError as e:
                st.error(f"⚠️ {e}")
                st.stop()

        st.session_state['semana_resultados']   = resultados
        st.session_state['semana_resultados_e2'] = resultados_e2
        st.session_state['semana_pallets_calc'] = dias_con_pedido
        st.session_state['semana_unavailable']  = unavailable

    # ── Resultados (persisten entre reruns hasta el próximo cálculo) ──
    if 'semana_resultados' in st.session_state:
        resultados       = st.session_state['semana_resultados']
        resultados_e2    = st.session_state.get('semana_resultados_e2', {})
        pallets_calc     = st.session_state['semana_pallets_calc']
        unavailable_calc = st.session_state.get('semana_unavailable', set())

        aviso_no_disp = ""
        if unavailable_calc:
            nombres = ", ".join(CARRIER_LABELS[c] for c in sorted(unavailable_calc))
            aviso_no_disp = f" — **sin {nombres}**"
        st.success(f"✅ Ruta óptima calculada para {len(resultados)} día(s){aviso_no_disp}")

        st.markdown("### Optimización normal")
        for dia in dias_ordenados:
            if dia in resultados:
                _render_day_result(dia, pallets_calc[dia], resultados[dia])

        st.divider()

        # ── Cuadro 2: Edwin Tráiler Azul con dos viajes sí o sí ──
        if resultados_e2:
            st.markdown("### Optimización con dos viajes Edwin")
            st.caption("El Edwin Tráiler Azul hace sí o sí un viaje lleno (24P) de Chigorodó y otro "
                       "lleno de Apartadó cada día. El resto se reparte de la forma más barata.")
            for dia in dias_ordenados:
                if dia in resultados_e2:
                    _render_day_result(dia, pallets_calc[dia], resultados_e2[dia])

            st.divider()

        # ── Consolidado de la semana ─────────────────────────────
        total_pallets = sum(sum(p.values()) for p in pallets_calc.values())
        total_costo   = sum(r['total_cost'] for r in resultados.values())
        total_e2      = sum(r['total_cost'] for r in resultados_e2.values()) if resultados_e2 else None

        st.markdown("### 📊 Consolidado de la semana")
        if total_e2 is None:
            c1, c2 = st.columns(2)
            c1.metric("Total pallets semana", f"{total_pallets}P")
            c2.metric("Costo total semana", money(total_costo))
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total pallets semana", f"{total_pallets}P")
            c2.metric("Optimización normal", money(total_costo))
            c3.metric("Con dos viajes Edwin", money(total_e2))
            diff = total_e2 - total_costo
            c4.metric("Diferencia", (f"+{money(diff)}" if diff > 0 else f"-{money(-diff)}" if diff < 0 else "$0"))
            if diff > 0:
                st.warning(f"En la semana, cumplirle los dos viajes al Edwin Tráiler Azul cuesta **{money(diff)} más** que la optimización normal.")
            elif diff < 0:
                st.success(f"En la semana, con los dos viajes del Edwin Tráiler Azul sale **{money(-diff)} más barato** que la optimización normal.")

        resumen_rows = []
        for dia in dias_ordenados:
            if dia in resultados:
                row = {
                    "Día":     dia,
                    "Pallets": sum(pallets_calc[dia].values()),
                    "Costo normal": money(resultados[dia]['total_cost']),
                }
                if dia in resultados_e2:
                    d2 = resultados_e2[dia]['total_cost'] - resultados[dia]['total_cost']
                    row["Con dos viajes Edwin"] = money(resultados_e2[dia]['total_cost'])
                    row["Diferencia"] = f"+{money(d2)}" if d2 > 0 else f"-{money(-d2)}" if d2 < 0 else "$0"
                resumen_rows.append(row)
        st.dataframe(pd.DataFrame(resumen_rows), use_container_width=True, hide_index=True)
