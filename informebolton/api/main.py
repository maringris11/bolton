import os
from pathlib import Path
from functools import lru_cache

import pandas as pd
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from fastapi import FastAPI, HTTPException, Query

# === Rutas base ===
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "config.yaml"

load_dotenv(BASE_DIR / ".env")


def load_config():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_host(configured_host: str) -> str:
    """Misma lógica que load_database.py / dashboard/src/db.py."""
    if not Path("/.dockerenv").exists() and configured_host == "host.docker.internal":
        return "localhost"
    return configured_host


@lru_cache(maxsize=1)
def get_engine():
    """Crea y cachea el engine de conexión a MySQL (se arma una sola vez)."""
    cfg = load_config()
    db = cfg["database"]
    host = _resolve_host(db["host"])

    url = URL.create(
        drivername=db.get("driver", "mysql+pymysql"),
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=host,
        port=db["port"],
        database=db["name"],
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


# === Funciones Core para Carga de Datos ===

def obtener_nombre_tabla_gold():
    """Nombre fijo de la tabla gold_final en MySQL."""
    return "gold_final"


def tabla_existe(nombre_tabla: str) -> bool:
    engine = get_engine()
    with engine.connect() as conn:
        resultado = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :tabla"
        ), {"tabla": nombre_tabla}).scalar()
    return resultado > 0


def cargar_datos_gold() -> pd.DataFrame:
    """Lee gold_final directamente desde MySQL (sin caché: siempre datos actuales)."""
    tabla = obtener_nombre_tabla_gold()
    if not tabla_existe(tabla):
        raise HTTPException(status_code=404, detail=f"No se encontró la tabla: {tabla}")

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM `{tabla}`"), conn)


def cargar_informe(nombre_informe: str) -> pd.DataFrame:
    """Lee un informe específico desde su tabla gold_<nombre_informe> en MySQL."""
    tabla = f"gold_{nombre_informe}"
    if not tabla_existe(tabla):
        raise HTTPException(status_code=404, detail=f"No se encontró la tabla: {tabla}")

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM `{tabla}`"), conn)


def preparar_dataframe_json(df):
    """Reemplaza nulos para que FastAPI (JSON) no falle con los NaN."""
    df = df.copy()
    df = df.astype(object).where(pd.notnull(df), None)
    return df


def procesar_respuesta_paginada(nombre_informe: str, page: int, limit: int):
    """Función central que pagina y estructura la respuesta de cualquier informe."""
    df = cargar_informe(nombre_informe)

    start = (page - 1) * limit
    end = start + limit
    df_paginado = df.iloc[start:end]
    df_paginado = preparar_dataframe_json(df_paginado)

    return {
        "informe": nombre_informe,
        "total_registros": len(df),
        "pagina_actual": page,
        "total_paginas": (len(df) + limit - 1) // limit,
        "columnas": len(df.columns),
        "data": df_paginado.to_dict(orient="records"),
    }



app = FastAPI(
    title="Informe Bolton API",
    description=("API para ver los informes de Bolton elaborados por: "
                 "ALEJANDRO MARIN, JUAN PABLO CASTILLO, "
                 "JOSEPH MARIN Y JOSE ALFREDO GONZALIAS"),
    version="2.0.0"
)


@app.get("/", tags=["Sistema"])
def inicio():
    return {
        "message": "Bienvenido a la API de Informe Bolton",
        "documentacion": "http://127.0.0.1:8000/docs",
        "gold_maestro": "/gold"
    }


@app.get("/health", tags=["Sistema"])
def health():
    tabla = obtener_nombre_tabla_gold()
    try:
        existe = tabla_existe(tabla)
        return {"status": "ok", "tabla_gold_existe": existe}
    except Exception as exc:
        return {"status": "error", "detalle": str(exc)}



@app.get("/gold", tags=["Data Maestra Gold"])
def consultar_gold(
    page: int = Query(1, ge=1, description="Número de página a consultar"),
    limit: int = Query(100, ge=1, le=1000, description="Cantidad de registros por página (máx 1000)")
):
    df = cargar_datos_gold()

    start = (page - 1) * limit
    end = start + limit
    df_paginado = df.iloc[start:end]
    df_paginado = preparar_dataframe_json(df_paginado)

    return {
        "total_registros": len(df),
        "pagina_actual": page,
        "registros_por_pagina": limit,
        "total_paginas": (len(df) + limit - 1) // limit,
        "columnas": len(df.columns),
        "nombres_columnas": df.columns.tolist(),
        "data": df_paginado.to_dict(orient="records"),
    }


@app.get("/gold/data", tags=["Data Maestra Gold"])
def consultar_gold_data(
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(100, ge=1, le=1000, description="Cantidad de registros (máx 1000)")
):
    df = cargar_datos_gold()

    start = (page - 1) * limit
    end = start + limit
    df_paginado = df.iloc[start:end]
    df_paginado = preparar_dataframe_json(df_paginado)

    return {
        "data": df_paginado.to_dict(orient="records"),
    }



@app.get("/informes/por-anio", tags=["Generales"])
def informe_por_anio(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("por_anio", page, limit)

@app.get("/informes/por-cuatrimestre", tags=["Generales"])
def informe_por_cuatrimestre(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("por_cuatrimestre", page, limit)

@app.get("/informes/top-ciudades", tags=["Top Anual"])
def informe_top_ciudades(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_ciudades", page, limit)

@app.get("/informes/top-productos", tags=["Top Anual"])
def informe_top_productos(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_productos", page, limit)

@app.get("/informes/top-vendedores", tags=["Top Anual"])
def informe_top_vendedores(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_vendedores", page, limit)

@app.get("/informes/top-ventas-per-capita", tags=["Per Cápita"])
def informe_top_ventas_per_capita(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_ventas_per_capita", page, limit)

@app.get("/informes/top-vendedores-per-capita", tags=["Per Cápita"])
def informe_top_vendedores_per_capita(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_vendedores_per_capita", page, limit)

@app.get("/informes/top-productos-cuatrimestre", tags=["Top Cuatrimestre"])
def informe_top_productos_cuatri(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_productos_cuatrimestre", page, limit)

@app.get("/informes/top-referencias-cuatrimestre", tags=["Top Cuatrimestre"])
def informe_top_referencias_cuatri(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_referencias_cuatrimestre", page, limit)

@app.get("/informes/top-familias-cuatrimestre", tags=["Top Cuatrimestre"])
def informe_top_familias_cuatri(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_familias_cuatrimestre", page, limit)

@app.get("/informes/top-categorias-cuatrimestre", tags=["Top Cuatrimestre"])
def informe_top_categorias_cuatri(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_categorias_cuatrimestre", page, limit)


@app.get("/informes/top-marca-region-cuatrimestre", tags=["Marcas"])
def informe_top_marca_region_cuatri(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_marca_region_cuatrimestre", page, limit)

@app.get("/informes/top-marca-region-anio", tags=["Marcas"])
def informe_top_marca_region_anio(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_marca_region_anio", page, limit)
