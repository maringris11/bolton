import sys
from pathlib import Path

DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src"
if str(DASHBOARD_SRC) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_SRC))

import plotly.express as px
import streamlit as st
from charts import PALETA_BOLTON
from db import check_connection, run_query
from queries import get_filtros_disponibles, get_top_anual

st.set_page_config(
    page_title="Regiones y Per Cápita · Bolton",
    page_icon="🗺️",
    layout="wide",
)

ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()

# --- Sidebar de filtros ---
with st.sidebar:
    st.header("Filtros Territoriales")
    anio_sel = st.selectbox(
        "Año a analizar",
        options=sorted(filtros["anios"], reverse=True),
    )
    metrica = st.radio(
        "Métrica de análisis",
        options=["pesos", "cajas"],
        format_func=lambda x: "Ingresos ($ COP)" if x == "pesos" else "Volumen (Cajas)",
        horizontal=True,
    )

st.title("🗺️ Desempeño Regional y Penetración Per Cápita")
st.markdown(
    f"Comparativa entre volumen bruto de ventas y consumo por habitante (cruzado con población DANE/API Colombia) en **{anio_sel}**."
)

df_reg_bruto = get_top_anual("top_ciudades", anio=anio_sel)
df_reg_pc = get_top_anual("top_ventas_per_capita", anio=anio_sel)

if df_reg_bruto.empty or df_reg_pc.empty:
    st.warning(f"No hay registros territoriales completos para el año {anio_sel}.")
    st.stop()

# --- KPIs Líderes Territoriales ---
lider_bruto = df_reg_bruto.iloc[0]
lider_pc = df_reg_pc.iloc[0]
col_pc = "pesos_per_capita" if metrica == "pesos" else "cajas_per_capita"

k1, k2, k3 = st.columns(3)
with k1:
    val_b = f"${lider_bruto['pesos']:,.0f}" if metrica == "pesos" else f"{lider_bruto['cajas']:,.0f} cajas"
    st.metric(
        "Región #1 en Volumen Total",
        lider_bruto["region"],
        delta=val_b,
    )
with k2:
    val_pc = (
        f"${lider_pc['pesos_per_capita']:,.2f} / hab"
        if metrica == "pesos"
        else f"{lider_pc['cajas_per_capita']:.4f} cajas / hab"
    )
    st.metric(
        "Región #1 Per Cápita",
        lider_pc["region"],
        delta=val_pc,
    )
with k3:
    pob_total = int(df_reg_pc["poblacion"].sum())
    st.metric("Población Cubierta (Top Regiones)", f"{pob_total:,} hab")

st.divider()

# --- 1. Comparativa Lado a Lado: Ventas Totales vs. Per Cápita ---
st.subheader("1. Ventas Totales vs. Ventas Per Cápita por Región")

c1, c2 = st.columns(2)
with c1:
    fig_bruto = px.bar(
        df_reg_bruto.sort_values(metrica, ascending=True),
        x=metrica,
        y="region",
        orientation="h",
        text_auto=".3s",
        title=f"Ranking por Volumen Bruto ({anio_sel})",
        labels={"region": "", metrica: "Pesos ($)" if metrica == "pesos" else "Cajas"},
        color_discrete_sequence=["#1B4965"],
    )
    fig_bruto.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
    st.plotly_chart(fig_bruto, use_container_width=True)

with c2:
    fig_pc = px.bar(
        df_reg_pc.sort_values(col_pc, ascending=True),
        x=col_pc,
        y="region",
        orientation="h",
        text_auto=".2f" if metrica == "pesos" else ".4f",
        title=f"Ranking Per Cápita ({anio_sel})",
        labels={
            "region": "",
            col_pc: "Pesos por Habitante ($)" if metrica == "pesos" else "Cajas por Habitante",
        },
        color_discrete_sequence=["#2A9D8F"],
    )
    fig_pc.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
    st.plotly_chart(fig_pc, use_container_width=True)

# --- 2. Matriz Población vs. Ventas (Burbuja de Oportunidad) ---
st.subheader("2. Matriz de Penetración: Población vs. Ventas")

fig_scatter = px.scatter(
    df_reg_pc,
    x="poblacion",
    y=metrica,
    size=col_pc,
    color="region",
    text="region",
    hover_data=["departamentos", "pesos_per_capita", "cajas_per_capita"],
    title=f"Tamaño de Mercado (Población) vs. Ventas · Tamaño de burbuja = Per Cápita ({anio_sel})",
    labels={
        "poblacion": "Población de la Región",
        metrica: "Pesos ($)" if metrica == "pesos" else "Cajas",
        "region": "Región",
    },
    color_discrete_sequence=PALETA_BOLTON,
)
fig_scatter.update_traces(textposition="top center")
fig_scatter.update_layout(height=450, margin=dict(t=50, b=20, l=20, r=20), showlegend=False)
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# --- 3. Desglose Cuatrimestral por Región (gold_final) ---
st.subheader(f"3. Estacionalidad Regional por Cuatrimestre ({anio_sel})")

df_reg_cuatri = run_query(
    """
    SELECT region, periodo_cuatrimestre,
           SUM(pesos) AS pesos,
           SUM(cajas) AS cajas
    FROM gold_final
    WHERE anio = :anio AND region IS NOT NULL
    GROUP BY region, periodo_cuatrimestre
    ORDER BY periodo_cuatrimestre, pesos DESC
    """,
    {"anio": int(anio_sel)},
)

if not df_reg_cuatri.empty:
    fig_cuatri_reg = px.bar(
        df_reg_cuatri,
        x="region",
        y=metrica,
        color="periodo_cuatrimestre",
        barmode="group",
        title=f"Comparativa Cuatrimestral por Región ({anio_sel})",
        labels={
            "region": "Región",
            metrica: "Pesos ($)" if metrica == "pesos" else "Cajas",
            "periodo_cuatrimestre": "Cuatrimestre",
        },
        color_discrete_sequence=PALETA_BOLTON,
    )
    fig_cuatri_reg.update_layout(height=400, margin=dict(t=50, b=20, l=20, r=20))
    st.plotly_chart(fig_cuatri_reg, use_container_width=True)

# --- Tabla detallada con departamentos y métricas per cápita ---
with st.expander("Ver tabla detallada con departamentos y población"):
    df_tabla = df_reg_pc[
        ["ranking", "region", "departamentos", "poblacion", "pesos", "cajas", "pesos_per_capita", "cajas_per_capita"]
    ].copy()
    df_tabla.columns = [
        "Rank PC",
        "Región",
        "Departamentos",
        "Población",
        "Pesos ($)",
        "Cajas",
        "Pesos / Hab ($)",
        "Cajas / Hab",
    ]
    st.dataframe(
        df_tabla.style.format(
            {
                "Población": "{:,}",
                "Pesos ($)": "${:,.0f}",
                "Cajas": "{:,.0f}",
                "Pesos / Hab ($)": "${:,.2f}",
                "Cajas / Hab": "{:.4f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )