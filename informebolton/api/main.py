from pathlib import Path
import pandas as pd
import yaml
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query

# === Rutas base ===
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "config.yaml"

def load_config():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# === Funciones Core para Carga de Datos ===

def obtener_ruta_gold():
    config = load_config()
    try:
        gold_dir = config['paths']['gold']
        gold_file = config['files']['gold']
    except KeyError as e:
        raise ValueError(f"Falta la clave {e} en el archivo de configuración.")
        
    return BASE_DIR / gold_dir / gold_file

@lru_cache(maxsize=1)
def cargar_datos_gold():
    """Carga el archivo maestro Gold desde el disco (cacheado en RAM)."""
    ruta_gold = obtener_ruta_gold()
    
    if not ruta_gold.exists():
        raise HTTPException(status_code=404, detail=f"No se encontró el archivo: {ruta_gold}")  
    
    return pd.read_csv(ruta_gold)

@lru_cache(maxsize=20)
def cargar_informe(nombre_informe: str) -> pd.DataFrame:
    """Carga un informe específico desde el disco (cacheado en RAM)."""
    config = load_config()
    try:
        gold_dir = config['paths']['gold']
        archivo = config['informes'][nombre_informe]
    except KeyError as e:
        raise ValueError(f"Falta la clave {e} en el archivo de configuración.")

    ruta_archivo = BASE_DIR / gold_dir / archivo
    
    if not ruta_archivo.exists():
        raise HTTPException(status_code=404, detail=f"No se encontró el archivo: {ruta_archivo}")  
    
    return pd.read_csv(ruta_archivo)

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

# === Configuración de FastAPI ===

app = FastAPI(
    title="Informe Bolton API", 
    description=("API para ver los informes de Bolton elaborados por: "
                 "ALEJANDRO MARIN, JUAN PABLO CASTILLO, "
                 "JOSEPH MARIN Y JOSE ALFREDO GONZALIAS"), 
    version="1.0.0"
)

# ==========================================
# ENDPOINTS BÁSICOS Y SISTEMA
# ==========================================

@app.get("/", tags=["Sistema"])
def inicio():
    return {
        "message": "Bienvenido a la API de Informe Bolton",
        "documentacion": "http://127.0.0.1:8000/docs",
        "gold_maestro": "/gold"
    }

@app.get("/health", tags=["Sistema"])
def health():
    ruta_gold = obtener_ruta_gold()
    return {
        "status": "ok", 
        "archivo_gold_maestro_existe": ruta_gold.exists()
    }

# ==========================================
# ENDPOINTS DEL DATASET MAESTRO (GOLD)
# ==========================================

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

# ==========================================
# ENDPOINTS DE INFORMES ESPECÍFICOS
# ==========================================

# --- Informes Generales ---

@app.get("/informes/por-anio", tags=["Generales"])
def informe_por_anio(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("por_anio", page, limit)

@app.get("/informes/por-cuatrimestre", tags=["Generales"])
def informe_por_cuatrimestre(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("por_cuatrimestre", page, limit)

# --- Top Anuales ---

@app.get("/informes/top-ciudades", tags=["Top Anual"])
def informe_top_ciudades(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_ciudades", page, limit)

@app.get("/informes/top-productos", tags=["Top Anual"])
def informe_top_productos(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_productos", page, limit)

@app.get("/informes/top-vendedores", tags=["Top Anual"])
def informe_top_vendedores(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_vendedores", page, limit)

# --- Per Cápita ---

@app.get("/informes/top-ventas-per-capita", tags=["Per Cápita"])
def informe_top_ventas_per_capita(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_ventas_per_capita", page, limit)

@app.get("/informes/top-vendedores-per-capita", tags=["Per Cápita"])
def informe_top_vendedores_per_capita(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_vendedores_per_capita", page, limit)

# --- Top por Cuatrimestre (Productos) ---

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

# --- Marcas ---

@app.get("/informes/top-marca-region-cuatrimestre", tags=["Marcas"])
def informe_top_marca_region_cuatri(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_marca_region_cuatrimestre", page, limit)

@app.get("/informes/top-marca-region-anio", tags=["Marcas"])
def informe_top_marca_region_anio(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=1000)):
    return procesar_respuesta_paginada("top_marca_region_anio", page, limit)