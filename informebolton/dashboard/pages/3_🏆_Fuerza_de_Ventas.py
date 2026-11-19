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
    page_title="Fuerza de Ventas · Bolton",
    page_icon="🏆",
    layout="wide",
)

ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()

# --- Sidebar de filtros ---
with st.sidebar:
    st.header("Filtros Comerciales")
    anio_sel = st.selectbox(
        "Año a analizar",
        options=sorted(filtros["anios"], reverse=True),
    )
    metrica = st.radio(
        "Métrica",
        options=["pesos", "cajas"],
        format_func=lambda x: "Ingresos ($ COP)" if x == "pesos" else "Volumen (Cajas)",
        horizontal=True,
    )

st.title("🏆 Rendimiento de la Fuerza de Ventas")
st.markdown(
    f"Ranking comercial por volumen bruto y eficiencia per cápita (excluyendo registros `SIN ASIGNAR`) en **{anio_sel}**."
)

df_vend = get_top_anual("top_vendedores", anio=anio_sel)
df_vend_pc = get_top_anual("top_vendedores_per_capita", anio=anio_sel)

# Calidad de asignación en gold_final
df_asig = run_query(
    """
    SELECT
        SUM(CASE WHEN vendedor = 'SIN ASIGNAR' THEN pesos ELSE 0 END) AS pesos_sin_asignar,
        SUM(pesos) AS pesos_totales
    FROM gold_final
    WHERE anio = :anio
    """,
    {"anio": int(anio_sel)},
)

if df_vend.empty:
    st.warning(f"No hay datos de vendedores para el año {anio_sel}.")
    st.stop()

# --- KPIs Ejecutivos ---
lider_v = df_vend.iloc[0]
lider_vpc = df_vend_pc.iloc[0] if not df_vend_pc.empty else None
col_pc = "pesos_per_capita" if metrica == "pesos" else "cajas_per_capita"

k1, k2, k3 = st.columns(3)
with k1:
    val_v = f"${lider_v['pesos']:,.0f}" if metrica == "pesos" else f"{lider_v['cajas']:,.0f} cajas"
    st.metric("Vendedor #1 (Volumen Bruto)", lider_v["vendedor"], delta=val_v)

with k2:
    if lider_vpc is not None:
        val_vpc = (
            f"${lider_vpc['pesos_per_capita']:,.2f} / hab"
            if metrica == "pesos"
            else f"{lider_vpc['cajas_per_capita']:.4f} cajas / hab"
        )
        st.metric("Vendedor #1 (Eficiencia Per Cápita)", lider_vpc["vendedor"], delta=val_vpc)

with k3:
    tot = float(df_asig["pesos_totales"].iloc[0] or 0)
    sin_asig = float(df_asig["pesos_sin_asignar"].iloc[0] or 0)
    pct_sin = (sin_asig / tot * 100) if tot > 0 else 0
    st.metric("Ventas 'SIN ASIGNAR'", f"${sin_asig:,.0f}", delta=f"{pct_sin:.1f}% del total", delta_color="off")

st.divider()

# --- 1. Rankings Comparados: Volumen Bruto vs. Per Cápita ---
st.subheader("1. Top Vendedores: Volumen Total vs. Penetración Per Cápita")

c1, c2 = st.columns(2)
with c1:
    fig_v = px.bar(
        df_vend.sort_values(metrica, ascending=True),
        x=metrica,
        y="vendedor",
        orientation="h",
        text_auto=".3s",
        title=f"Top 10 Vendedores por Volumen ({anio_sel})",
        labels={"vendedor": "", metrica: "Pesos ($)" if metrica == "pesos" else "Cajas"},
        color_discrete_sequence=["#1B4965"],
    )
    fig_v.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
    st.plotly_chart(fig_v, use_container_width=True)

with c2:
    if not df_vend_pc.empty:
        fig_vpc = px.bar(
            df_vend_pc.sort_values(col_pc, ascending=True),
            x=col_pc,
            y="vendedor",
            orientation="h",
            text_auto=".2f" if metrica == "pesos" else ".4f",
            title=f"Top 10 Vendedores Per Cápita ({anio_sel})",
            labels={
                "vendedor": "",
                col_pc: "Pesos / Hab ($)" if metrica == "pesos" else "Cajas / Hab",
            },
            color_discrete_sequence=["#2A9D8F"],
        )
        fig_vpc.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig_vpc, use_container_width=True)

st.divider()

# --- 2. Evolución por Cuatrimestre del Top Vendedores (gold_final) ---
st.subheader(f"2. Desempeño Cuatrimestral por Vendedor ({anio_sel})")

top_nombres = df_vend["vendedor"].tolist()
vendedores_sel = st.multiselect(
    "Selecciona vendedores para comparar por cuatrimestre:",
    options=top_nombres,
    default=top_nombres[:5],
)

if vendedores_sel:
    placeholders = ", ".join(f":v{i}" for i in range(len(vendedores_sel)))
    params = {"anio": int(anio_sel), **{f"v{i}": v for i, v in enumerate(vendedores_sel)}}

    df_v_cuatri = run_query(
        f"""
        SELECT vendedor, periodo_cuatrimestre,
               SUM(pesos) AS pesos,
               SUM(cajas) AS cajas,
               COUNT(DISTINCT cliente) AS clientes_activos
        FROM gold_final
        WHERE anio = :anio AND vendedor IN ({placeholders})
        GROUP BY vendedor, periodo_cuatrimestre
        ORDER BY periodo_cuatrimestre, pesos DESC
        """,
        params,
    )

    if not df_v_cuatri.empty:
        fig_vc = px.bar(
            df_v_cuatri,
            x="periodo_cuatrimestre",
            y=metrica,
            color="vendedor",
            barmode="group",
            title=f"Evolución Cuatrimestral ({anio_sel})",
            labels={
                "periodo_cuatrimestre": "Cuatrimestre",
                metrica: "Pesos ($)" if metrica == "pesos" else "Cajas",
                "vendedor": "Vendedor",
            },
            color_discrete_sequence=PALETA_BOLTON,
        )
        fig_vc.update_layout(height=400, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig_vc, use_container_width=True)

# --- Tabla consolidada de eficiencia ---
if not df_vend_pc.empty:
    with st.expander("Ver tabla detallada de eficiencia per cápita por vendedor"):
        df_t = df_vend_pc[
            ["ranking", "vendedor", "poblacion", "meses_con_datos", "pesos", "cajas", "pesos_per_capita", "cajas_per_capita"]
        ].copy()
        df_t.columns = [
            "Rank PC",
            "Vendedor",
            "Población Territorio",
            "Meses Activos",
            "Pesos ($)",
            "Cajas",
            "Pesos / Hab ($)",
            "Cajas / Hab",
        ]
        st.dataframe(
            df_t.style.format(
                {
                    "Población Territorio": "{:,}",
                    "Pesos ($)": "${:,.0f}",
                    "Cajas": "{:,.0f}",
                    "Pesos / Hab ($)": "${:,.2f}",
                    "Cajas / Hab": "{:.4f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )