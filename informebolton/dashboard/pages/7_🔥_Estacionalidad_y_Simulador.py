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
    page_title="Estacionalidad y Simulador · Bolton",
    page_icon="🔥",
    layout="wide",
)

ok, msg = check_connection()
if not ok:
    st.error(msg)
    st.stop()

filtros = get_filtros_disponibles()

NOMBRES_MESES = {
    1: "01 - Ene", 2: "02 - Feb", 3: "03 - Mar", 4: "04 - Abr",
    5: "05 - May", 6: "06 - Jun", 7: "07 - Jul", 8: "08 - Ago",
    9: "09 - Sep", 10: "10 - Oct", 11: "11 - Nov", 12: "12 - Dic",
}

st.title("🔥 Mapa de Calor Estacional y Simulador 'What-If'")
st.markdown(
    "Detecta patrones históricos de temporada alta/baja y proyecta escenarios comerciales sobre `gold_final`."
)

tab_heat, tab_sim = st.tabs(["🔥 Mapa de Calor Estacional", "🎛️ Simulador 'What-If'"])

# ==============================================================================
# PESTAÑA 1: MAPA DE CALOR ESTACIONAL (HEATMAP)
# ==============================================================================
with tab_heat:
    c_f1, c_f2, c_f3 = st.columns([2, 2, 1])
    with c_f1:
        vista_heatmap = st.selectbox(
            "Cruzar Meses contra:",
            options=["Años (Histórico)", "Regiones (Geográfico)", "Canales de Venta"],
        )
    with c_f2:
        regiones_hm = st.multiselect(
            "Filtrar por Región (opcional):",
            options=filtros["regiones"],
            default=[],
            placeholder="Todas las regiones",
        )
    with c_f3:
        metrica_hm = st.radio(
            "Métrica:",
            options=["pesos", "cajas"],
            format_func=lambda x: "Pesos ($)" if x == "pesos" else "Cajas",
            horizontal=True,
        )

    # Filtro opcional de año si cruza Meses vs Regiones o Canales
    anio_hm = None
    if vista_heatmap != "Años (Histórico)":
        anio_hm = st.selectbox(
            "Selecciona el Año a inspeccionar:",
            options=sorted(filtros["anios"], reverse=True),
        )

    conds, params = ["mes IS NOT NULL"], {}
    if regiones_hm:
        r_holders = ", ".join(f":r{i}" for i in range(len(regiones_hm)))
        for i, r in enumerate(regiones_hm):
            params[f"r{i}"] = r
        conds.append(f"region IN ({r_holders})")
    if anio_hm is not None:
        conds.append("anio = :anio")
        params["anio"] = int(anio_hm)

    where_hm = "WHERE " + " AND ".join(conds)

    if vista_heatmap == "Años (Histórico)":
        col_eje_y = "anio"
        etiqueta_y = "Año"
    elif vista_heatmap == "Regiones (Geográfico)":
        col_eje_y = "region"
        etiqueta_y = "Región"
    else:
        col_eje_y = "canal"
        etiqueta_y = "Canal"

    df_hm = run_query(
        f"""
        SELECT
            CAST(`{col_eje_y}` AS CHAR) AS eje_y,
            mes,
            SUM(pesos) AS pesos,
            SUM(cajas) AS cajas
        FROM gold_final
        {where_hm}
        GROUP BY `{col_eje_y}`, mes
        ORDER BY eje_y, mes
        """,
        params,
    )

    if df_hm.empty:
        st.warning("No hay datos suficientes para construir el mapa de calor con estos filtros.")
    else:
        df_hm["mes_nombre"] = df_hm["mes"].map(NOMBRES_MESES)
        matriz = df_hm.pivot(index="eje_y", columns="mes_nombre", values=metrica_hm).fillna(0)
        # Asegurar orden cronológico de columnas 01-Ene a 12-Dic
        cols_ordenadas = [NOMBRES_MESES[m] for m in range(1, 13) if NOMBRES_MESES[m] in matriz.columns]
        matriz = matriz[cols_ordenadas]

        fig_hm = px.imshow(
            matriz,
            text_auto=".2s",
            aspect="auto",
            color_continuous_scale="YlOrRd",
            labels=dict(x="Mes", y=etiqueta_y, color="Pesos ($)" if metrica_hm == "pesos" else "Cajas"),
            title=f"Intensidad de {'Ingresos ($)' if metrica_hm == 'pesos' else 'Cajas'} · Meses vs. {etiqueta_y}",
        )
        fig_hm.update_layout(height=460, margin=dict(t=55, b=20, l=20, r=20))
        st.plotly_chart(fig_hm, use_container_width=True)

        # Hallazgos automáticos de estacionalidad
        totales_mes = df_hm.groupby("mes_nombre")[metrica_hm].sum()
        mes_pico = totales_mes.idxmax()
        mes_valle = totales_mes.idxmin()
        h1, h2 = st.columns(2)
        h1.success(f"📈 **Mes Pico de Temporada Alta:** `{mes_pico}` ({totales_mes.max():,.0f})")
        h2.info(f"📉 **Mes Valle de Temporada Baja:** `{mes_valle}` ({totales_mes.min():,.0f})")


# ==============================================================================
# PESTAÑA 2: SIMULADOR INTERACTIVO "WHAT-IF"
# ==============================================================================
with tab_sim:
    st.subheader("Simulador de Escenarios Comerciales")
    st.markdown(
        "Ajusta los deslizadores para proyectar cómo cambiaría la facturación total de Bolton "
        "si aplicas metas de crecimiento en volumen (cajas) o ajuste de precio/ticket promedio."
    )

    anio_base = st.selectbox(
        "Año base para la simulación:",
        options=sorted(filtros["anios"], reverse=True),
        key="sim_anio",
    )

    # Cargar base agrupada por región y canal desde gold_final
    df_base = run_query(
        """
        SELECT
            COALESCE(region, 'SIN REGIÓN') AS region,
            COALESCE(canal, 'SIN CANAL') AS canal,
            SUM(cajas) AS cajas_base,
            SUM(pesos) AS pesos_base
        FROM gold_final
        WHERE anio = :anio
        GROUP BY region, canal
        """,
        {"anio": int(anio_base)},
    )

    if df_base.empty:
        st.warning(f"No hay datos en `gold_final` para simular el año {anio_base}.")
        st.stop()

    st.divider()
    s1, s2, s3 = st.columns(3)

    with s1:
        crec_global_cajas = st.slider(
            "📦 Variación Global en Volumen (Cajas %)",
            min_value=-30,
            max_value=50,
            value=5,
            step=1,
            help="Aplica un crecimiento o caída porcentual en cajas a toda la compañía.",
        )

    with s2:
        ajuste_precio = st.slider(
            "💲 Ajuste de Precio / Ticket Promedio (%)",
            min_value=-20,
            max_value=30,
            value=3,
            step=1,
            help="Simula un incremento de precios o mejora de mix.",
        )

    with s3:
        region_impulso = st.selectbox(
            "🚀 Región con Impulso Extra:",
            options=["Ninguna"] + sorted(df_base["region"].unique().tolist()),
        )
        boost_region = st.slider(
            "Impulso adicional en Región seleccionada (%)",
            min_value=0,
            max_value=50,
            value=15 if region_impulso != "Ninguna" else 0,
            step=1,
            disabled=(region_impulso == "Ninguna"),
        )

    # --- Cálculo de la simulación ---
    df_sim = df_base.copy()
    factor_cajas = 1 + (crec_global_cajas / 100.0)
    factor_precio = 1 + (ajuste_precio / 100.0)

    df_sim["factor_extra"] = df_sim["region"].apply(
        lambda r: (1 + boost_region / 100.0) if (region_impulso != "Ninguna" and r == region_impulso) else 1.0
    )

    df_sim["cajas_proyectadas"] = df_sim["cajas_base"] * factor_cajas * df_sim["factor_extra"]
    df_sim["pesos_proyectados"] = df_sim["pesos_base"] * factor_cajas * factor_precio * df_sim["factor_extra"]

    tot_pesos_base = df_sim["pesos_base"].sum()
    tot_pesos_proy = df_sim["pesos_proyectados"].sum()
    diff_pesos = tot_pesos_proy - tot_pesos_base
    pct_pesos = (diff_pesos / tot_pesos_base * 100) if tot_pesos_base > 0 else 0

    tot_cajas_base = df_sim["cajas_base"].sum()
    tot_cajas_proy = df_sim["cajas_proyectadas"].sum()
    diff_cajas = tot_cajas_proy - tot_cajas_base

    st.divider()
    k1, k2, k3 = st.columns(3)
    k1.metric(f"Facturación Real ({anio_base})", f"${tot_pesos_base:,.0f}")
    k2.metric(
        "Facturación Simulada ($)",
        f"${tot_pesos_proy:,.0f}",
        delta=f"${diff_pesos:+,.0f} ({pct_pesos:+.1f}%)",
    )
    k3.metric(
        "Cajas Simuladas",
        f"{tot_cajas_proy:,.0f}",
        delta=f"{diff_cajas:+,.0f} cajas",
    )

    # Comparativa visual Real vs Simulado por Región
    df_reg_comp = (
        df_sim.groupby("region", as_index=False)[["pesos_base", "pesos_proyectados"]]
        .sum()
        .sort_values("pesos_proyectados", ascending=False)
    )
    df_melt = df_reg_comp.melt(
        id_vars="region",
        value_vars=["pesos_base", "pesos_proyectados"],
        var_name="Escenario",
        value_name="Pesos",
    )
    df_melt["Escenario"] = df_melt["Escenario"].map(
        {"pesos_base": f"Real {anio_base}", "pesos_proyectados": "Escenario Simulado"}
    )

    fig_sim = px.bar(
        df_melt,
        x="region",
        y="Pesos",
        color="Escenario",
        barmode="group",
        text_auto=".3s",
        title="Impacto por Región: Real vs. Escenario Simulado",
        labels={"region": "Región", "Pesos": "Ingresos ($ COP)"},
        color_discrete_sequence=["#94A3B8", "#2A9D8F"],
    )
    fig_sim.update_layout(height=420, margin=dict(t=50, b=20, l=20, r=20))
    st.plotly_chart(fig_sim, use_container_width=True)