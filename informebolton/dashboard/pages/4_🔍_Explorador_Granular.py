import io
import sys
from pathlib import Path

DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src"
if str(DASHBOARD_SRC) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_SRC))

import pandas as pd
import plotly.express as px
import streamlit as st
from charts import PALETA_BOLTON
from db import check_connection, run_query
from queries import get_filtros_disponibles

st.set_page_config(
    page_title="Explorador Granular · Bolton",
    page_icon="🔍",
    layout="wide",
)

ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()
canales = run_query(
    "SELECT DISTINCT canal FROM gold_final WHERE canal IS NOT NULL ORDER BY canal"
)["canal"].tolist()
marcas = run_query(
    "SELECT DISTINCT marca FROM gold_final WHERE marca IS NOT NULL ORDER BY marca"
)["marca"].tolist()

# --- Sidebar de Filtros Cruzados ---
with st.sidebar:
    st.header("Filtros Granulares (`gold_final`)")
    anio_sel = st.selectbox(
        "Año",
        options=sorted(filtros["anios"], reverse=True),
    )
    periodos_anio = [p for p in filtros["periodos"] if p.startswith(str(anio_sel))]
    cuatri_sel = st.multiselect(
        "Cuatrimestre(s)",
        options=periodos_anio,
        default=periodos_anio,
    )
    regiones_sel = st.multiselect("Región(es)", options=filtros["regiones"], default=[])
    canales_sel = st.multiselect("Canal(es)", options=canales, default=[])
    marcas_sel = st.multiselect("Marca(s)", options=marcas, default=[])
    categorias_sel = st.multiselect("Categoría(s)", options=filtros["categorias"], default=[])

st.title("🔍 Explorador Granular y Exportación (`gold_final`)")
st.markdown(
    "Consulta dinámica sobre la tabla de hechos en MySQL con agrupación a medida y descarga directa."
)

# --- Construcción segura de cláusula WHERE ---
condiciones = ["anio = :anio"]
params: dict = {"anio": int(anio_sel)}


def _add_in_filter(col_name: str, values: list, prefix: str):
    if values:
        holders = ", ".join(f":{prefix}_{i}" for i in range(len(values)))
        for i, val in enumerate(values):
            params[f"{prefix}_{i}"] = val
        condiciones.append(f"`{col_name}` IN ({holders})")


_add_in_filter("periodo_cuatrimestre", cuatri_sel, "per")
_add_in_filter("region", regiones_sel, "reg")
_add_in_filter("canal", canales_sel, "can")
_add_in_filter("marca", marcas_sel, "mar")
_add_in_filter("categoria", categorias_sel, "cat")

where_sql = "WHERE " + " AND ".join(condiciones)

# --- 1. KPIs del corte seleccionado ---
df_kpis = run_query(
    f"""
    SELECT
        COUNT(*) AS transacciones,
        COUNT(DISTINCT cliente) AS clientes_unicos,
        COALESCE(SUM(pesos), 0) AS total_pesos,
        COALESCE(SUM(cajas), 0) AS total_cajas
    FROM gold_final
    {where_sql}
    """,
    params,
)

kpi = df_kpis.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ingresos del Corte ($)", f"${kpi['total_pesos']:,.0f}")
c2.metric("Volumen Cajas", f"{kpi['total_cajas']:,.0f}")
c3.metric("Clientes Únicos", f"{int(kpi['clientes_unicos']):,}")
c4.metric("Registros Filtrados", f"{int(kpi['transacciones']):,}")

st.divider()

# --- 2. Agrupador Dinámico (Pivot rápido) ---
st.subheader("1. Agrupación Dinámica de Negocio")

dim_opciones = {
    "Canal": "canal",
    "Región": "region",
    "Departamento": "departamentos",
    "Marca": "marca",
    "Categoría": "categoria",
    "Familia": "familia",
    "Producto": "producto",
    "Cliente": "cliente",
    "Vendedor": "vendedor",
    "Cuatrimestre": "periodo_cuatrimestre",
    "Mes": "mes",
}

g1, g2, g3 = st.columns([2, 2, 1])
with g1:
    dim_label = st.selectbox("Agrupar por:", options=list(dim_opciones.keys()), index=0)
with g2:
    metrica_din = st.selectbox(
        "Ordenar por métrica:",
        options=["pesos", "cajas", "transacciones"],
        format_func=lambda x: {"pesos": "Ingresos ($ COP)", "cajas": "Cajas", "transacciones": "N° Registros"}[x],
    )
with g3:
    top_k = st.number_input("Mostrar Top N:", min_value=5, max_value=100, value=15, step=5)

col_dim = dim_opciones[dim_label]

df_agg = run_query(
    f"""
    SELECT
        COALESCE(CAST(`{col_dim}` AS CHAR), 'SIN DATO') AS grupo,
        SUM(pesos) AS pesos,
        SUM(cajas) AS cajas,
        COUNT(*) AS transacciones,
        COUNT(DISTINCT cliente) AS clientes
    FROM gold_final
    {where_sql}
    GROUP BY `{col_dim}`
    ORDER BY {metrica_din} DESC
    LIMIT :limite
    """,
    {**params, "limite": int(top_k)},
)

if not df_agg.empty:
    v1, v2 = st.columns([3, 2])
    with v1:
        fig_din = px.bar(
            df_agg.sort_values(metrica_din, ascending=True),
            x=metrica_din,
            y="grupo",
            orientation="h",
            text_auto=".3s",
            title=f"Top {top_k} por {dim_label} ({anio_sel})",
            labels={"grupo": dim_label, metrica_din: metrica_din.capitalize()},
            color_discrete_sequence=PALETA_BOLTON,
        )
        fig_din.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig_din, use_container_width=True)

    with v2:
        df_show = df_agg.copy()
        df_show.columns = [dim_label, "Pesos ($)", "Cajas", "Registros", "Clientes"]
        st.dataframe(
            df_show.style.format({"Pesos ($)": "${:,.0f}", "Cajas": "{:,.0f}", "Registros": "{:,}", "Clientes": "{:,}"}),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

st.divider()

# --- 3. Muestra de Registros y Exportación CSV / Excel ---
st.subheader("2. Vista Previa Transaccional y Descarga")

limite_tabla = st.slider("Filas máximas a previsualizar / exportar:", 100, 10000, 1000, step=100)

df_detalle = run_query(
    f"""
    SELECT anio, mes, periodo_cuatrimestre, region, departamentos, zona,
           canal, cliente, vendedor, marca, categoria, familia, producto,
           referencia, gr, cajas, pesos
    FROM gold_final
    {where_sql}
    ORDER BY anio DESC, mes DESC, pesos DESC
    LIMIT :lim_det
    """,
    {**params, "lim_det": int(limite_tabla)},
)

st.dataframe(df_detalle, use_container_width=True, hide_index=True, height=340)

if not df_detalle.empty:
    d1, d2 = st.columns(2)
    with d1:
        csv_bytes = df_detalle.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="⬇️ Descargar corte en CSV",
            data=csv_bytes,
            file_name=f"bolton_gold_{anio_sel}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_detalle.to_excel(writer, index=False, sheet_name="Gold_Bolton")
        st.download_button(
            label="⬇️ Descargar corte en Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"bolton_gold_{anio_sel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )