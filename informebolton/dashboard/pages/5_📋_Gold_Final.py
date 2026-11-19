import io
import sys
from pathlib import Path

DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src"
if str(DASHBOARD_SRC) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_SRC))

import pandas as pd
import streamlit as st
from db import check_connection, run_query
from queries import get_filtros_disponibles

st.set_page_config(
    page_title="Gold Final · Bolton",
    page_icon="📋",
    layout="wide",
)

ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()
marcas = run_query(
    "SELECT DISTINCT marca FROM gold_final WHERE marca IS NOT NULL ORDER BY marca"
)["marca"].tolist()

# --- Sidebar de Filtros Sencillos ---
with st.sidebar:
    st.header("Filtros · Gold Final")
    anio_sel = st.selectbox(
        "Año",
        options=["Todos"] + sorted(filtros["anios"], reverse=True),
        index=1,  # Por defecto selecciona el año más reciente
    )

    if anio_sel != "Todos":
        periodos_disp = [p for p in filtros["periodos"] if p.startswith(str(anio_sel))]
    else:
        periodos_disp = filtros["periodos"]

    cuatri_sel = st.selectbox("Cuatrimestre", options=["Todos"] + periodos_disp)
    region_sel = st.selectbox("Región", options=["Todas"] + filtros["regiones"])
    marca_sel = st.selectbox("Marca", options=["Todas"] + marcas)
    limite = st.slider("Filas a mostrar", min_value=50, max_value=5000, value=500, step=50)

st.title("📋 Tabla Maestra · Gold Final")
st.markdown("Vista directa y sencilla de los registros consolidados en la tabla `gold_final` de MySQL.")

# --- Construcción de filtros SQL ---
condiciones = []
params: dict = {}

if anio_sel != "Todos":
    condiciones.append("anio = :anio")
    params["anio"] = int(anio_sel)

if cuatri_sel != "Todos":
    condiciones.append("periodo_cuatrimestre = :periodo")
    params["periodo"] = cuatri_sel

if region_sel != "Todas":
    condiciones.append("region = :region")
    params["region"] = region_sel

if marca_sel != "Todas":
    condiciones.append("marca = :marca")
    params["marca"] = marca_sel

where_sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

# --- KPIs Rápidos ---
df_resumen = run_query(
    f"""
    SELECT
        COUNT(*) AS filas,
        COALESCE(SUM(pesos), 0) AS total_pesos,
        COALESCE(SUM(cajas), 0) AS total_cajas
    FROM gold_final
    {where_sql}
    """,
    params,
)

res = df_resumen.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("Total Registros", f"{int(res['filas']):,}")
c2.metric("Total Ingresos ($)", f"${res['total_pesos']:,.0f}")
c3.metric("Total Cajas", f"{res['total_cajas']:,.0f}")

st.divider()

# --- Consulta a gold_final ---
df_gold = run_query(
    f"""
    SELECT
        id, anio, mes, periodo_cuatrimestre,
        region, departamentos, zona,
        canal, cliente, vendedor,
        marca, categoria, familia, producto, referencia,
        gr, cajas, cajas_valida, pesos, poblacion_total
    FROM gold_final
    {where_sql}
    ORDER BY anio DESC, mes DESC, id DESC
    LIMIT :limite
    """,
    {**params, "limite": int(limite)},
)

# Buscador rápido de texto sobre los resultados cargados
busqueda = st.text_input(
    "🔎 Buscar dentro de los resultados (cliente, producto, vendedor, departamento...):",
    placeholder="Escribe para filtrar la tabla...",
)

if busqueda.strip():
    mask = df_gold.astype(str).apply(
        lambda col: col.str.contains(busqueda.strip(), case=False, na=False)
    ).any(axis=1)
    df_mostrar = df_gold[mask]
else:
    df_mostrar = df_gold

st.caption(f"Mostrando **{len(df_mostrar):,}** de **{int(res['filas']):,}** registros totales.")

st.dataframe(
    df_mostrar,
    use_container_width=True,
    hide_index=True,
    height=460,
)

# --- Descarga directa ---
if not df_mostrar.empty:
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            label="⬇️ Descargar vista en CSV",
            data=df_mostrar.to_csv(index=False).encode("utf-8-sig"),
            file_name="gold_final_bolton.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_mostrar.to_excel(writer, index=False, sheet_name="gold_final")
        st.download_button(
            label="⬇️ Descargar vista en Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="gold_final_bolton.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )