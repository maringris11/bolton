import sys
import unicodedata
from pathlib import Path

DASHBOARD_SRC = Path(__file__).resolve().parents[1] / "src"
if str(DASHBOARD_SRC) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_SRC))

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from db import check_connection, run_query
from queries import get_filtros_disponibles

st.set_page_config(
    page_title="Mapa de Colombia · Bolton",
    page_icon="🇨🇴",
    layout="wide",
)

GEOJSON_URL = (
    "https://gist.githubusercontent.com/john-guerra/"
    "43c7656821069d00dcbc/raw/be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/"
    "Colombia.geo.json"
)


def _normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    return " ".join(s.upper().strip().split())


# Equivalencias entre nombres de API Colombia / gold_final y el GeoJSON de departamentos
ALIAS_GEOJSON = {
    "BOGOTA": "SANTAFE DE BOGOTA D.C",
    "BOGOTA D.C.": "SANTAFE DE BOGOTA D.C",
    "BOGOTA, D.C.": "SANTAFE DE BOGOTA D.C",
    "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA": (
        "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA"
    ),
    "SAN ANDRES Y PROVIDENCIA": (
        "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA"
    ),
}


@st.cache_data(ttl=86400, show_spinner="Cargando cartografía de Colombia...")
def cargar_geojson_colombia():
    resp = requests.get(GEOJSON_URL, timeout=15)
    resp.raise_for_status()
    geo = resp.json()
    for feat in geo.get("features", []):
        nombre_raw = feat.get("properties", {}).get("NOMBRE_DPT", "")
        feat["properties"]["dpto_norm"] = _normalizar_texto(nombre_raw)
    return geo


ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()

# --- Sidebar de filtros ---
with st.sidebar:
    st.header("Filtros del Mapa")
    anio_sel = st.selectbox(
        "Año a analizar",
        options=sorted(filtros["anios"], reverse=True),
    )
    periodos_anio = [p for p in filtros["periodos"] if p.startswith(str(anio_sel))]
    periodo_sel = st.selectbox("Cuatrimestre", options=["Todos"] + periodos_anio)

    modo_mapa = st.radio(
        "Variable a visualizar en el mapa",
        options=["pesos", "cajas", "pesos_per_capita", "cajas_per_capita"],
        format_func=lambda x: {
            "pesos": "Ventas Totales ($ COP)",
            "cajas": "Volumen Total (Cajas)",
            "pesos_per_capita": "Ventas Per Cápita ($ / Hab)",
            "cajas_per_capita": "Cajas Per Cápita (Cajas / Hab)",
        }[x],
    )

st.title("🇨🇴 Mapa Coroplético de Ventas por Departamento")
st.markdown(
    f"Distribución geográfica de ventas y penetración per cápita en Colombia · **{anio_sel}** ({periodo_sel})."
)

# --- Consulta a gold_final + silver_areas para desagregar departamentos individuales ---
condiciones = ["g.anio = :anio", "g.departamentos IS NOT NULL"]
params: dict = {"anio": int(anio_sel)}

if periodo_sel != "Todos":
    condiciones.append("g.periodo_cuatrimestre = :periodo")
    params["periodo"] = periodo_sel

where_sql = "WHERE " + " AND ".join(condiciones)

df_raw = run_query(
    f"""
    SELECT
        g.region,
        g.departamentos,
        g.n_departamentos,
        g.poblacion_total,
        SUM(g.pesos) AS pesos,
        SUM(g.cajas) AS cajas
    FROM gold_final g
    {where_sql}
    GROUP BY g.region, g.departamentos, g.n_departamentos, g.poblacion_total
    """,
    params,
)

# Población individual por departamento desde silver_areas (cargada desde API Colombia)
df_areas = run_query("SELECT departamento, poblacion FROM silver_areas")
pob_por_depto = {
    _normalizar_texto(row["departamento"]): float(row["poblacion"] or 0)
    for _, row in df_areas.iterrows()
}

if df_raw.empty:
    st.warning(f"No hay datos geográficos disponibles para {anio_sel} ({periodo_sel}).")
    st.stop()

# --- Desagregar regiones multidepartamento (ej. COSTA, EJE CAFETERO, SANTANDERES) ---
# Si una región agrupa varios departamentos, distribuimos proporcionalmente por población
filas_deptos = []
for _, row in df_raw.iterrows():
    lista_dptos = [d.strip() for d in str(row["departamentos"]).split(",") if d.strip()]
    if len(lista_dptos) == 1:
        d_norm = _normalizar_texto(lista_dptos[0])
        pob = pob_por_depto.get(d_norm, float(row["poblacion_total"] or 0))
        filas_deptos.append({
            "departamento": lista_dptos[0],
            "dpto_geo": ALIAS_GEOJSON.get(d_norm, d_norm),
            "region": row["region"],
            "pesos": float(row["pesos"]),
            "cajas": float(row["cajas"]),
            "poblacion": pob,
        })
    else:
        pobs = [pob_por_depto.get(_normalizar_texto(d), 0.0) for d in lista_dptos]
        suma_pob = sum(pobs)
        for d, p_ind in zip(lista_dptos, pobs):
            d_norm = _normalizar_texto(d)
            factor = (p_ind / suma_pob) if suma_pob > 0 else (1.0 / len(lista_dptos))
            filas_deptos.append({
                "departamento": d,
                "dpto_geo": ALIAS_GEOJSON.get(d_norm, d_norm),
                "region": row["region"],
                "pesos": float(row["pesos"]) * factor,
                "cajas": float(row["cajas"]) * factor,
                "poblacion": p_ind,
            })

df_mapa = (
    pd.DataFrame(filas_deptos)
    .groupby(["departamento", "dpto_geo", "region"], as_index=False)
    .agg(pesos=("pesos", "sum"), cajas=("cajas", "sum"), poblacion=("poblacion", "max"))
)

df_mapa["pesos_per_capita"] = df_mapa.apply(
    lambda r: (r["pesos"] / r["poblacion"]) if r["poblacion"] > 0 else 0.0, axis=1
)
df_mapa["cajas_per_capita"] = df_mapa.apply(
    lambda r: (r["cajas"] / r["poblacion"]) if r["poblacion"] > 0 else 0.0, axis=1
)

# --- Renderizado del Mapa ---
try:
    geojson_col = cargar_geojson_colombia()
except Exception as e:
    st.error(f"No se pudo descargar el GeoJSON de Colombia (requiere conexión a internet): {e}")
    st.stop()

etiquetas = {
    "pesos": "Ventas ($ COP)",
    "cajas": "Cajas",
    "pesos_per_capita": "Pesos / Hab ($)",
    "cajas_per_capita": "Cajas / Hab",
}

col_mapa, col_top = st.columns([3, 2])

with col_mapa:
    fig = px.choropleth(
        df_mapa,
        geojson=geojson_col,
        locations="dpto_geo",
        featureidkey="properties.dpto_norm",
        color=modo_mapa,
        hover_name="departamento",
        hover_data={
            "dpto_geo": False,
            "region": True,
            "poblacion": ":,.0f",
            "pesos": ":$,.0f",
            "cajas": ":,.0f",
            "pesos_per_capita": ":$,.2f",
            "cajas_per_capita": ":.4f",
        },
        color_continuous_scale="YlGnBu",
        labels={modo_mapa: etiquetas[modo_mapa], "region": "Región", "poblacion": "Población"},
        title=f"{etiquetas[modo_mapa]} por Departamento · {anio_sel}",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(height=580, margin=dict(t=50, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

with col_top:
    st.subheader("Ranking Departamental")
    df_rank = df_mapa.sort_values(modo_mapa, ascending=False)[
        ["departamento", "region", "pesos", "cajas", "pesos_per_capita"]
    ].copy()
    df_rank.columns = ["Departamento", "Región", "Pesos ($)", "Cajas", "Pesos / Hab"]
    st.dataframe(
        df_rank.style.format(
            {"Pesos ($)": "${:,.0f}", "Cajas": "{:,.0f}", "Pesos / Hab": "${:,.2f}"}
        ),
        use_container_width=True,
        hide_index=True,
        height=540,
    )

st.caption(
    "Nota: Para regiones que agrupan múltiples departamentos en la capa Silver/Gold "
    "(como Costa, Eje Cafetero o Santanderes), el valor departamental se pondera según la población oficial de `silver_areas`."
)