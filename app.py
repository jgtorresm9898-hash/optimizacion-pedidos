"""
Punto de entrada de la app — define las dos páginas y la navegación.
"""
import streamlit as st
from page_diario import render as render_diario
from page_semanal import render as render_semanal

st.set_page_config(
    page_title="Optimización de Pedidos — La Hacienda",
    page_icon="🍌",
    layout="wide",
)

pagina_diaria = st.Page(
    render_diario,
    title="Ruta óptima del día",
    icon="🍌",
    url_path="ruta-diaria",
    default=True,
)
pagina_semanal = st.Page(
    render_semanal,
    title="Optimización semanal",
    icon="📅",
    url_path="optimizacion-semanal",
)

pg = st.navigation([pagina_diaria, pagina_semanal])
pg.run()
