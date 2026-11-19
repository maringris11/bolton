import pandas as pd
import plotly.express as px

PALETA_BOLTON = ["#1B4965", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", "#457B9D"]


def grafico_evolucion_anual(df_anual: pd.DataFrame, metrica: str = "pesos"):
    titulo = "Ventas Totales por Año (COP)" if metrica == "pesos" else "Volumen de Cajas por Año"
    etiqueta_y = "Pesos ($)" if metrica == "pesos" else "Cajas"

    df = df_anual.copy()
    df["anio_str"] = df["anio"].astype(str)
    df["estado"] = df["meses_con_datos"].apply(
        lambda m: f"Completo ({m}m)" if m == 12 else f"Parcial ({m}m)"
    )

    fig = px.bar(
        df,
        x="anio_str",
        y=metrica,
        color="estado",
        text_auto=".3s",
        title=titulo,
        labels={"anio_str": "Año", metrica: etiqueta_y, "estado": "Cobertura"},
        color_discrete_sequence=["#1B4965", "#F4A261"],
    )
    fig.update_layout(height=380, margin=dict(t=50, b=20, l=20, r=20), legend_title_text="")
    return fig


def grafico_cuatrimestral(df_cuatri: pd.DataFrame, metrica: str = "pesos"):
    titulo = "Comparativa por Cuatrimestre (COP)" if metrica == "pesos" else "Cajas por Cuatrimestre"
    etiqueta_y = "Pesos ($)" if metrica == "pesos" else "Cajas"

    df = df_cuatri.copy()
    df["anio_str"] = df["anio"].astype(str)
    df["cuatri_label"] = "C" + df["cuatrimestre"].astype(str)

    fig = px.bar(
        df,
        x="cuatri_label",
        y=metrica,
        color="anio_str",
        barmode="group",
        text_auto=".3s",
        title=titulo,
        labels={"cuatri_label": "Cuatrimestre", metrica: etiqueta_y, "anio_str": "Año"},
        color_discrete_sequence=PALETA_BOLTON,
    )
    fig.update_layout(height=380, margin=dict(t=50, b=20, l=20, r=20))
    return fig


def grafico_evolucion_mensual(df_mensual: pd.DataFrame, metrica: str = "pesos"):
    titulo = "Tendencia Mensual Comparada (YoY)"
    etiqueta_y = "Pesos ($)" if metrica == "pesos" else "Cajas"

    df = df_mensual.copy()
    df["anio_str"] = df["anio"].astype(str)

    fig = px.line(
        df,
        x="mes",
        y=metrica,
        color="anio_str",
        markers=True,
        title=titulo,
        labels={"mes": "Mes", metrica: etiqueta_y, "anio_str": "Año"},
        color_discrete_sequence=PALETA_BOLTON,
    )
    fig.update_xaxes(dtick=1)
    fig.update_layout(height=380, margin=dict(t=50, b=20, l=20, r=20))
    return fig


def grafico_top_horizontal(df_top: pd.DataFrame, col_nombre: str, titulo: str, metrica: str = "pesos"):
    df = df_top.sort_values(metrica, ascending=True)
    fig = px.bar(
        df,
        x=metrica,
        y=col_nombre,
        orientation="h",
        text_auto=".3s",
        title=titulo,
        labels={col_nombre: "", metrica: "Pesos ($)" if metrica == "pesos" else "Cajas"},
        color_discrete_sequence=["#2A9D8F"],
    )
    fig.update_layout(height=400, margin=dict(t=50, b=20, l=20, r=20))
    return fig