"""
Página: Ruta óptima del día.

Calculadora simple — se ingresan los pallets por finca de un solo día y
se devuelve la ruta (vehículos + costo) más barata para despacharlos.
"""
import streamlit as st
from daily_optimizer import optimize_day, ALL_FARMS


def money(n):
    return f"${n:,.0f}".replace(",", ".")


FARM_LABELS = {
    'JUANA PIO':     'Juana Pío',
    'DOÑA FRANCIA':  'Doña Francia',
    'SANTA MARIA':   'Santa María',
    'CHISPERO':      'Chispero',
    'SALVAMENTO':    'Salvamento',
    'SAN BARTOLO':   'San Bartolo',
}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]


def render():
    st.markdown("""
    <style>
        .block-container { padding-top: 2rem; max-width: 760px; }
        div[data-testid="stNumberInput"] label { font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    # ── Encabezado ───────────────────────────────────────────────
    col_title, col_logo = st.columns([3, 2])
    with col_title:
        st.markdown("## 🍌 Ruta óptima del día")
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

    # ── Día ──────────────────────────────────────────────────────
    dia = st.selectbox("Día", DIAS, label_visibility="visible")

    st.markdown(f"### Pedido {dia}")
    st.caption("Escribe los pallets de cada finca. Deja en 0 la finca que no tenga pedido ese día.")

    # ── Pallets por finca ────────────────────────────────────────
    pallets = {}
    for farm in ALL_FARMS:
        pallets[farm] = st.number_input(
            FARM_LABELS[farm], min_value=0, step=1, value=0, key=f"pallets_{farm}",
        )

    st.divider()

    calcular = st.button("▶  Calcular ruta óptima", type="primary", use_container_width=True)

    if calcular:
        if sum(pallets.values()) == 0:
            st.warning("Ingresa al menos una finca con pallets antes de calcular.")
            st.stop()

        with st.spinner("Calculando la ruta más económica… con pedidos grandes puede tardar unos segundos."):
            resultado = optimize_day(pallets)

        st.success(f"✅ Ruta óptima calculada para **{dia}**")

        st.markdown("#### Ruta")
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

        st.markdown("#### Total del día")
        c1, c2 = st.columns(2)
        c1.metric("Total pallets", f"{sum(pallets.values())}P")
        c2.metric("Costo total", money(resultado['total_cost']))
