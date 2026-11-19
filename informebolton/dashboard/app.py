import sys
from pathlib import Path

DASHBOARD_SRC = Path(__file__).resolve().parent / "src"
if str(DASHBOARD_SRC) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_SRC))

import streamlit as st
from charts import (
    grafico_cuatrimestral,
    grafico_evolucion_anual,
    grafico_evolucion_mensual,
    grafico_top_horizontal,
)
from db import check_connection
from queries import (
    get_evolucion_mensual,
    get_filtros_disponibles,
    get_resumen_anual,
    get_resumen_cuatrimestral,
    get_top_anual,
    get_top_cuatrimestre,
)
st.set_page_config(
    page_title="Bolton · Business Intelligence",
    page_icon="📊",
    layout="wide",
)

# --- Verificación de conexión MySQL `bolton` ---
ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

# --- Barra lateral (Filtros Globales) ---
filtros = get_filtros_disponibles()

with st.sidebar:
    st.title("📊 Bolton BI")
    st.caption(msg)
    st.divider()

    anios_sel = st.multiselect(
        "Años a comparar",
        options=filtros["anios"],
        default=filtros["anios"],
    )
    if not anios_sel:
        anios_sel = filtros["anios"]

    anio_foco = st.selectbox(
        "Año foco (Rankings y Tops)",
        options=sorted(anios_sel, reverse=True),
    )

    periodos_anio = [p for p in filtros["periodos"] if p.startswith(str(anio_foco))]
    periodo_sel = st.selectbox(
        "Cuatrimestre foco",
        options=["Todos"] + periodos_anio,
    )

    regiones_sel = st.multiselect(
        "Filtrar Regiones (Tendencia)",
        options=filtros["regiones"],
        default=[],
        placeholder="Todas las regiones",
    )

    metrica = st.radio(
        "Métrica principal",
        options=["pesos", "cajas"],
        format_func=lambda x: "Ingresos ($ COP)" if x == "pesos" else "Volumen (Cajas)",
        horizontal=True,
    )

# --- Encabezado y KPIs ---
st.title("Panel Ejecutivo de Ventas · Bolton")
st.markdown("Análisis conectado en tiempo real a la capa **Gold** en MySQL (`bolton`).")

df_anual = get_resumen_anual()
df_foco = df_anual[df_anual["anio"] == anio_foco].iloc[0]
df_prev = df_anual[df_anual["anio"] == (anio_foco - 1)]

meses_foco = int(df_foco["meses_con_datos"])
if meses_foco < 12:
    st.warning(
        f"⚠️ El año **{anio_foco}** tiene datos parciales (**{meses_foco} de 12 meses**). "
        "Revisa el promedio mensual para compararlo de forma justa contra años completos."
    )

col1, col2, col3, col4 = st.columns(4)
with col1:
    delta_pesos = None
    if not df_prev.empty and df_prev["pesos"].iloc[0] > 0:
        var = ((df_foco["pesos"] - df_prev["pesos"].iloc[0]) / df_prev["pesos"].iloc[0]) * 100
        delta_pesos = f"{var:+.1f}% vs {anio_foco - 1}"
    st.metric(f"Ventas {anio_foco} ($)", f"${df_foco['pesos']:,.0f}", delta=delta_pesos)

with col2:
    st.metric(f"Cajas {anio_foco}", f"{df_foco['cajas']:,.0f}")

with col3:
    st.metric("Promedio Mensual ($)", f"${df_foco['promedio_mensual_pesos']:,.0f}")

with col4:
    st.metric("Transacciones Gold", f"{int(df_foco['n_registros']):,}")

st.divider()

# --- Gráficos de Evolución Temporal ---
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(
        grafico_evolucion_anual(df_anual[df_anual["anio"].isin(anios_sel)], metrica),
        use_container_width=True,
    )
with c2:
    df_cuatri = get_resumen_cuatrimestral(anios_sel)
    st.plotly_chart(
        grafico_cuatrimestral(df_cuatri, metrica),
        use_container_width=True,
    )

df_mensual = get_evolucion_mensual(anios_sel, regiones_sel or None)
st.plotly_chart(grafico_evolucion_mensual(df_mensual, metrica), use_container_width=True)

st.divider()

# --- Comparativa de Productos y Regiones (Informes Gold) ---
st.subheader(f"Tops de Negocio · {anio_foco} ({periodo_sel})")
t1, t2 = st.columns(2)

with t1:
    nivel_prod = st.selectbox(
        "Nivel de portafolio (Cuatrimestre)",
        options=["productos", "categorias", "familias", "referencias"],
        format_func=str.capitalize,
    )
    df_top_prod = get_top_cuatrimestre(
        nivel=nivel_prod,
        periodo=periodo_sel if periodo_sel != "Todos" else None,
        anio=anio_foco,
    )
    if not df_top_prod.empty:
        # Si seleccionó "Todos" los cuatrimestres del año, agrupamos para el ranking anual
        df_plot = (
            df_top_prod.groupby("item", as_index=False)[["pesos", "cajas"]].sum()
            .sort_values(metrica, ascending=False)
            .head(10)
        )
        st.plotly_chart(
            grafico_top_horizontal(df_plot, "item", f"Top {nivel_prod.capitalize()} ({periodo_sel})", metrica),
            use_container_width=True,
        )

with t2:
    df_top_reg = get_top_anual("top_ciudades", anio=anio_foco)
    if not df_top_reg.empty:
        st.plotly_chart(
            grafico_top_horizontal(df_top_reg.head(10), "region", f"Top Regiones ({anio_foco})", metrica),
            use_container_width=True,
        )