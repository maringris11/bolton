import pandas as pd
from db import run_query


def get_filtros_disponibles() -> dict:
    """Obtiene años, cuatrimestres, regiones y categorías disponibles en gold_final."""
    anios = run_query("SELECT DISTINCT anio FROM gold_por_anio ORDER BY anio")["anio"].tolist()
    periodos = run_query(
        "SELECT DISTINCT periodo_cuatrimestre FROM gold_por_cuatrimestre ORDER BY periodo_cuatrimestre"
    )["periodo_cuatrimestre"].tolist()
    regiones = run_query(
        "SELECT DISTINCT region FROM gold_final WHERE region IS NOT NULL ORDER BY region"
    )["region"].tolist()
    categorias = run_query(
        "SELECT DISTINCT categoria FROM gold_final WHERE categoria IS NOT NULL ORDER BY categoria"
    )["categoria"].tolist()
    return {
        "anios": anios,
        "periodos": periodos,
        "regiones": regiones,
        "categorias": categorias,
    }


def get_resumen_anual() -> pd.DataFrame:
    return run_query("""
        SELECT anio, pesos, cajas, n_registros, meses_con_datos,
               ROUND(pesos / NULLIF(meses_con_datos, 0), 2) AS promedio_mensual_pesos,
               ROUND(cajas / NULLIF(meses_con_datos, 0), 2) AS promedio_mensual_cajas
        FROM gold_por_anio
        ORDER BY anio
    """)


def get_resumen_cuatrimestral(anios: list[int] | None = None) -> pd.DataFrame:
    if anios:
        placeholders = ", ".join(f":a{i}" for i in range(len(anios)))
        params = {f"a{i}": int(a) for i, a in enumerate(anios)}
        sql = f"""
            SELECT anio, cuatrimestre, periodo_cuatrimestre,
                   pesos, cajas, n_registros, meses_con_datos
            FROM gold_por_cuatrimestre
            WHERE anio IN ({placeholders})
            ORDER BY anio, cuatrimestre
        """
        return run_query(sql, params)
    return run_query("""
        SELECT anio, cuatrimestre, periodo_cuatrimestre,
               pesos, cajas, n_registros, meses_con_datos
        FROM gold_por_cuatrimestre
        ORDER BY anio, cuatrimestre
    """)


def get_top_cuatrimestre(nivel: str, periodo: str | None = None, anio: int | None = None) -> pd.DataFrame:
    """
    nivel: 'productos' | 'referencias' | 'familias' | 'categorias'
    Consulta las tablas gold_top_<nivel>_cuatrimestre.
    """
    tablas_validas = {
        "productos": ("gold_top_productos_cuatrimestre", "producto"),
        "referencias": ("gold_top_referencias_cuatrimestre", "referencia"),
        "familias": ("gold_top_familias_cuatrimestre", "familia"),
        "categorias": ("gold_top_categorias_cuatrimestre", "categoria"),
    }
    tabla, col = tablas_validas[nivel]
    condiciones, params = [], {}
    if periodo and periodo != "Todos":
        condiciones.append("periodo_cuatrimestre = :periodo")
        params["periodo"] = periodo
    if anio:
        condiciones.append("anio = :anio")
        params["anio"] = int(anio)

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return run_query(f"""
        SELECT anio, cuatrimestre, periodo_cuatrimestre, `{col}` AS item,
               pesos, cajas, meses_con_datos, participacion_pesos, ranking
        FROM `{tabla}`
        {where}
        ORDER BY anio, cuatrimestre, ranking
    """, params)


def get_top_anual(tabla_suffix: str, anio: int | None = None) -> pd.DataFrame:
    """Consulta gold_top_productos, gold_top_ciudades, gold_top_vendedores, etc."""
    tabla = f"gold_{tabla_suffix}"
    if anio:
        return run_query(
            f"SELECT * FROM `{tabla}` WHERE anio = :anio ORDER BY ranking",
            {"anio": int(anio)},
        )
    return run_query(f"SELECT * FROM `{tabla}` ORDER BY anio, ranking")


def get_marca_lider_region(granularidad: str = "anio", anio: int | None = None) -> pd.DataFrame:
    tabla = "gold_top_marca_region_anio" if granularidad == "anio" else "gold_top_marca_region_cuatrimestre"
    if anio:
        return run_query(
            f"SELECT * FROM `{tabla}` WHERE anio = :anio ORDER BY region, ranking",
            {"anio": int(anio)},
        )
    return run_query(f"SELECT * FROM `{tabla}` ORDER BY anio, region, ranking")


def get_evolucion_mensual(anios: list[int], regiones: list[str] | None = None) -> pd.DataFrame:
    """Consulta agregada sobre gold_final usando el índice idx_gf_anio_mes."""
    a_holders = ", ".join(f":a{i}" for i in range(len(anios)))
    params = {f"a{i}": int(a) for i, a in enumerate(anios)}
    where_reg = ""
    if regiones:
        r_holders = ", ".join(f":r{i}" for i in range(len(regiones)))
        for i, r in enumerate(regiones):
            params[f"r{i}"] = r
        where_reg = f"AND region IN ({r_holders})"

    return run_query(f"""
        SELECT anio, mes, cuatrimestre, periodo_cuatrimestre,
               SUM(pesos) AS pesos,
               SUM(cajas) AS cajas,
               COUNT(*) AS transacciones
        FROM gold_final
        WHERE anio IN ({a_holders}) {where_reg}
        GROUP BY anio, mes, cuatrimestre, periodo_cuatrimestre
        ORDER BY anio, mes
    """, params)