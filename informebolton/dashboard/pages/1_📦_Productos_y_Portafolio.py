import sys
from pathlib import Path

DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src"
if str(DASHBOARD_SRC) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_SRC))

import plotly.express as px
import streamlit as st
from charts import PALETA_BOLTON, grafico_top_horizontal
from db import check_connection, run_query
from queries import (
    get_filtros_disponibles,
    get_marca_lider_region,
    get_top_anual,
    get_top_cuatrimestre,
)

st.set_page_config(
    page_title="Productos y Portafolio · Bolton",
    page_icon="📦",
    layout="wide",
)

ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()

# --- Sidebar de filtros ---
with st.sidebar:
    st.header("Filtros de Portafolio")
    anio_sel = st.selectbox(
        "Año a analizar",
        options=sorted(filtros["anios"], reverse=True),
    )
    periodos_anio = [p for p in filtros["periodos"] if p.startswith(str(anio_sel))]
    periodo_sel = st.selectbox(
        "Cuatrimestre",
        options=["Todos"] + periodos_anio,
    )
    metrica = st.radio(
        "Métrica",
        options=["pesos", "cajas"],
        format_func=lambda x: "Ingresos ($ COP)" if x == "pesos" else "Volumen (Cajas)",
        horizontal=True,
    )

st.title("📦 Análisis de Productos, Marcas y Portafolio")
st.markdown(
    f"Desempeño por jerarquía de producto y dominio de marca por región para **{anio_sel}** ({periodo_sel})."
)

# --- 1. Comparativa de las 4 jerarquías en el cuatrimestre ---
st.subheader("1. Ranking por Jerarquía de Producto (Cuatrimestre)")

tab_cat, tab_fam, tab_prod, tab_ref = st.tabs(
    ["Categorías", "Familias", "Productos", "Referencias"]
)

niveles = [
    (tab_cat, "categorias", "Categoría"),
    (tab_fam, "familias", "Familia"),
    (tab_prod, "productos", "Producto"),
    (tab_ref, "referencias", "Referencia"),
]

for tab, clave, etiqueta in niveles:
    with tab:
        df_nivel = get_top_cuatrimestre(
            nivel=clave,
            periodo=periodo_sel if periodo_sel != "Todos" else None,
            anio=anio_sel,
        )
        if df_nivel.empty:
            st.info(f"Sin datos de {etiqueta.lower()} para el filtro seleccionado.")
            continue

        c1, c2 = st.columns([3, 2])
        with c1:
            if periodo_sel == "Todos":
                df_agg = (
                    df_nivel.groupby("item", as_index=False)[["pesos", "cajas"]]
                    .sum()
                    .sort_values(metrica, ascending=False)
                    .head(10)
                )
                st.plotly_chart(
                    grafico_top_horizontal(df_agg, "item", f"Top {etiqueta}s en {anio_sel}", metrica),
                    use_container_width=True,
                )
            else:
                st.plotly_chart(
                    grafico_top_horizontal(
                        df_nivel, "item", f"Top {etiqueta}s · {periodo_sel}", metrica
                    ),
                    use_container_width=True,
                )

        with c2:
            # Evolución cuatrimestral dentro del año seleccionado
            fig_evol = px.bar(
                df_nivel,
                x="periodo_cuatrimestre",
                y=metrica,
                color="item",
                barmode="group",
                title=f"Comportamiento por Cuatrimestre ({anio_sel})",
                labels={"periodo_cuatrimestre": "Cuatrimestre", metrica: metrica.capitalize(), "item": etiqueta},
                color_discrete_sequence=PALETA_BOLTON,
            )
            fig_evol.update_layout(height=400, margin=dict(t=50, b=20, l=20, r=20))
            st.plotly_chart(fig_evol, use_container_width=True)

        # Tabla con participación porcentual (si se filtró un cuatrimestre específico)
        if periodo_sel != "Todos":
            df_tabla = df_nivel[["ranking", "item", "pesos", "cajas", "participacion_pesos"]].copy()
            df_tabla["participacion_pesos"] = (df_tabla["participacion_pesos"] * 100).round(2)
            df_tabla.columns = ["Ranking", etiqueta, "Pesos ($)", "Cajas", "Participación (%)"]
            st.dataframe(
                df_tabla.style.format({"Pesos ($)": "${:,.0f}", "Cajas": "{:,.0f}", "Participación (%)": "{:.2f}%"}),
                use_container_width=True,
                hide_index=True,
            )

st.divider()

# --- 2. Marca Líder por Región ---
st.subheader("2. Marca Líder por Región y Participación de Mercado")

granularidad = "anio" if periodo_sel == "Todos" else "cuatrimestre"
df_marcas = get_marca_lider_region(granularidad=granularidad, anio=anio_sel)

if periodo_sel != "Todos" and not df_marcas.empty:
    df_marcas = df_marcas[df_marcas["periodo_cuatrimestre"] == periodo_sel]

if not df_marcas.empty:
    m1, m2 = st.columns([3, 2])
    with m1:
        fig_marca = px.bar(
            df_marcas.sort_values(metrica, ascending=True),
            x=metrica,
            y="region",
            color="marca",
            orientation="h",
            text_auto=".3s",
            title=f"Marca #1 por Región · {anio_sel} ({periodo_sel})",
            labels={"region": "Región", metrica: "Pesos ($)" if metrica == "pesos" else "Cajas", "marca": "Marca Líder"},
            color_discrete_sequence=PALETA_BOLTON,
        )
        fig_marca.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig_marca, use_container_width=True)

    with m2:
        df_m_tabla = df_marcas[["region", "marca", "pesos", "cajas", "participacion_pesos"]].copy()
        df_m_tabla["participacion_pesos"] = (df_m_tabla["participacion_pesos"] * 100).round(1)
        df_m_tabla.columns = ["Región", "Marca Líder", "Pesos ($)", "Cajas", "Share Región (%)"]
        st.dataframe(
            df_m_tabla.sort_values("Pesos ($)", ascending=False).style.format(
                {"Pesos ($)": "${:,.0f}", "Cajas": "{:,.0f}", "Share Región (%)": "{:.1f}%"}
            ),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

st.divider()

# --- 3. Comparativa Interanual de Top Productos (gold_top_productos) ---
st.subheader("3. Evolución Interanual de Top Productos")
df_top_hist = get_top_anual("top_productos")
if not df_top_hist.empty:
    productos_disponibles = sorted(df_top_hist["producto"].unique())
    prods_comp = st.multiselect(
        "Selecciona productos para comparar su trayectoria entre años:",
        options=productos_disponibles,
        default=productos_disponibles[:4],
    )
    if prods_comp:
        df_comp = df_top_hist[df_top_hist["producto"].isin(prods_comp)].copy()
        df_comp["anio_str"] = df_comp["anio"].astype(str)
        fig_hist = px.line(
            df_comp,
            x="anio_str",
            y=metrica,
            color="producto",
            markers=True,
            title="Trayectoria Anual de Productos Destacados",
            labels={"anio_str": "Año", metrica: "Pesos ($)" if metrica == "pesos" else "Cajas", "producto": "Producto"},
            color_discrete_sequence=PALETA_BOLTON,
        )
        fig_hist.update_layout(height=380, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig_hist, use_container_width=True)