"""
Punto de entrada de la app — define las páginas y la navegación.
"""
import streamlit as st
from page_diario import render as render_diario
from page_ruta_semana import render as render_ruta_semana

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
pagina_ruta_semana = st.Page(
    render_ruta_semana,
    title="Ruta óptima — Semana",
    icon="🗓️",
    url_path="ruta-semana",
)

pg = st.navigation([pagina_diaria, pagina_ruta_semana])
pg.run()
