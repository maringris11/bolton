import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
import os
from dotenv import load_dotenv
import pandas as pd
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
load_dotenv() 
ROOT = Path(__file__).resolve().parents[2]   # .../informebolton
log = logging.getLogger(__name__)

COLS_BOLTON = [
    "anio", "mes", "fecha", "semana_anio", "semana_mes", "factura", "documento",
    "nombre_cliente", "canal", "articulo", "marca", "texto_breve_material",
    "producto", "referencia", "gr", "familia", "categoria", "punto", "ciudad",
    "zona", "vendedor", "inv", "demand_forecast", "presupuesto", "cajas",
    "pesos", "euros",
]

COLS_DEPTOS = {   
    "id": "VARCHAR(20)", "name": "VARCHAR(100)", "description": "TEXT",
    "city_capital_id": "VARCHAR(20)", "municipalities": "VARCHAR(20)",
    "surface": "VARCHAR(30)", "population": "VARCHAR(30)",
    "phone_prefix": "VARCHAR(20)", "country_id": "VARCHAR(20)",
    "city_capital": "TEXT", "country": "TEXT", "cities": "TEXT",
    "region_id": "VARCHAR(20)", "region": "TEXT", "natural_areas": "TEXT",
    "maps": "TEXT", "indigenous_reservations": "TEXT", "airports": "TEXT",
}

INFORMES = [
    "por_anio", "por_cuatrimestre", "top_ciudades", "top_productos",
    "top_vendedores", "top_ventas_per_capita", "top_vendedores_per_capita",
    "top_productos_cuatrimestre", "top_referencias_cuatrimestre",
    "top_familias_cuatrimestre", "top_categorias_cuatrimestre",
    "top_marca_region_cuatrimestre", "top_marca_region_anio",
]

COL_TYPES = {
    "anio": "SMALLINT", "cuatrimestre": "TINYINT", "periodo_cuatrimestre": "VARCHAR(10)",
    "region": "VARCHAR(100)", "departamentos": "VARCHAR(255)",
    "producto": "VARCHAR(255)", "referencia": "VARCHAR(255)",
    "familia": "VARCHAR(100)", "categoria": "VARCHAR(100)",
    "marca": "VARCHAR(100)", "vendedor": "VARCHAR(150)",
    "pesos": "DOUBLE", "cajas": "DOUBLE",
    "n_registros": "INT", "meses_con_datos": "TINYINT",
    "poblacion": "BIGINT", "pesos_per_capita": "DOUBLE", "cajas_per_capita": "DOUBLE",
    "participacion_pesos": "DOUBLE", "ranking": "SMALLINT",
}
def load():
    with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db, paths, files = cfg["database"], cfg["paths"], cfg["files"]

    # Las credenciales ya no vienen del yaml, sino del .env
    db["user"] = os.environ["DB_USER"]
    db["password"] = os.environ["DB_PASSWORD"]
    host = db["host"]
    if not Path("/.dockerenv").exists() and host == "host.docker.internal":
        host = "localhost"

    # Crear la base de datos si no existe (conexión sin database)
    admin = create_engine(URL.create(
        drivername=db["driver"], username=db["user"], password=db["password"],
        host=host, port=db["port"], query={"charset": "utf8mb4"},
    ))
    with admin.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db['name']}` "
                          "CHARACTER SET utf8mb4"))

    engine = create_engine(URL.create(
        drivername=db["driver"], username=db["user"], password=db["password"],
        host=host, port=db["port"], database=db["name"],
        query={"charset": "utf8mb4"},
    ))

    bronze_dir = ROOT / paths["bronze"]
    silver_dir = ROOT / paths["silver"]
    gold_dir = ROOT / paths["gold"]

    def bronze():
        # 1. Si la tabla existe se elimina y se vuelve a crear
        col_defs = ", ".join(f"`{c}` VARCHAR(255)" for c in COLS_BOLTON)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS bronze_bolton"))
            conn.execute(text(f"""
                CREATE TABLE bronze_bolton (
                    {col_defs},
                    _load_ts DATETIME,
                    _source_file VARCHAR(255)
                ) CHARACTER SET utf8mb4
            """))

        # 2. Leer el Excel de bronze (todo como texto, tal cual viene)
        bolton_file = bronze_dir / files["bolton_bronze"]
        if not bolton_file.exists():
            raise FileNotFoundError(f"No existe {bolton_file}")
        try:
            df = pd.read_excel(bolton_file, dtype=str, engine="calamine")
        except ImportError:
            df = pd.read_excel(bolton_file, dtype=str, engine="openpyxl")

        # Quitar columnas sin encabezado (vacías)
        df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

        if len(df.columns) != len(COLS_BOLTON):
            raise ValueError(f"Se esperaban {len(COLS_BOLTON)} columnas y "
                             f"el archivo trae {len(df.columns)}: {list(df.columns)}")
        df.columns = COLS_BOLTON
        df = df.astype(object).where(df.notna(), None)   # vacíos -> NULL
        df["_load_ts"] = datetime.now()
        df["_source_file"] = files["bolton_bronze"]

        # 3. Insertar
        df.to_sql("bronze_bolton", engine, if_exists="append",
                  index=False, chunksize=5000, method="multi")

        # 4. Verificar
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM bronze_bolton")).scalar()
        if n != len(df):
            raise RuntimeError(f"bronze_bolton: archivo={len(df)} tabla={n}")
        log.info("bronze_bolton cargado desde archivo: %d filas", n)

                # --- departamentos.csv -> bronze_departamentos ---
        col_defs = ", ".join(f"`{c}` {t}" for c, t in COLS_DEPTOS.items())
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS bronze_departamentos"))
            conn.execute(text(f"""
                CREATE TABLE bronze_departamentos (
                    {col_defs},
                    _load_ts DATETIME,
                    _source_file VARCHAR(255)
                ) CHARACTER SET utf8mb4
            """))

        deptos_file = bronze_dir / files["areas_bronze"]
        if not deptos_file.exists():
            raise FileNotFoundError(f"No existe {deptos_file}")

        df = pd.read_csv(deptos_file, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        if len(df.columns) != len(COLS_DEPTOS):
            raise ValueError(f"Se esperaban {len(COLS_DEPTOS)} columnas y "
                             f"el archivo trae {len(df.columns)}: {list(df.columns)}")
        df.columns = list(COLS_DEPTOS)
        df = df.astype(object).where(df != "", None)   # vacíos -> NULL
        df["_load_ts"] = datetime.now()
        df["_source_file"] = files["areas_bronze"]

        df.to_sql("bronze_departamentos", engine, if_exists="append",
                  index=False, chunksize=500, method="multi")

        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM bronze_departamentos")).scalar()
        if n != len(df):
            raise RuntimeError(f"bronze_departamentos: archivo={len(df)} tabla={n}")
        log.info("bronze_departamentos cargado desde archivo: %d filas", n)

    def silver():
        # 1. Si la tabla existe se elimina y se vuelve a crear
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS silver_areas"))
            conn.execute(text("""
                CREATE TABLE silver_areas (
                    departamento VARCHAR(100),
                    superficie INT,
                    poblacion BIGINT,
                    ciudad_capital VARCHAR(100)
                ) CHARACTER SET utf8mb4
            """))

        # 2. Leer el CSV limpio de silver
        areas_file = silver_dir / files["areas_silver"]
        if not areas_file.exists():
            raise FileNotFoundError(f"No existe {areas_file}")

        df = pd.read_csv(areas_file, encoding="utf-8")
        df = df.astype(object).where(df.notna(), None)   # NaN -> NULL

        # 3. Insertar
        df.to_sql("silver_areas", engine, if_exists="append",
                  index=False, chunksize=500, method="multi")

        # 4. Verificar
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM silver_areas")).scalar()
        if n != len(df):
            raise RuntimeError(f"silver_areas: archivo={len(df)} tabla={n}")
        log.info("silver_areas cargado desde archivo: %d filas", n)

                # --- bolton_silver.csv -> silver_bolton ---
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS silver_bolton"))
            conn.execute(text("""
                CREATE TABLE silver_bolton (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    anio SMALLINT,
                    mes TINYINT,
                    cliente VARCHAR(255),
                    canal VARCHAR(100),
                    vendedor VARCHAR(150),
                    region VARCHAR(100),
                    zona VARCHAR(100),
                    producto VARCHAR(255),
                    referencia VARCHAR(255),
                    marca VARCHAR(100),
                    familia VARCHAR(100),
                    categoria VARCHAR(100),
                    gr DECIMAL(10,2),
                    cajas DECIMAL(12,2),
                    cajas_valida BOOLEAN,
                    pesos DOUBLE
                ) CHARACTER SET utf8mb4
            """))

        bolton_file = silver_dir / files["bolton_silver"]
        if not bolton_file.exists():
            raise FileNotFoundError(f"No existe {bolton_file}")

        df = pd.read_csv(bolton_file, encoding="utf-8")
        df = df.astype(object).where(df.notna(), None)   # NaN -> NULL

        df.to_sql("silver_bolton", engine, if_exists="append",
                  index=False, chunksize=5000, method="multi")

        # Índices después de la carga (más rápido que insertar con índices)
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX idx_sb_anio_mes ON silver_bolton (anio, mes)"))
            conn.execute(text("CREATE INDEX idx_sb_region ON silver_bolton (region)"))
            conn.execute(text("CREATE INDEX idx_sb_marca ON silver_bolton (marca)"))

        # Verificar: conteo y suma de pesos contra el archivo
        with engine.connect() as conn:
            n, total = conn.execute(
                text("SELECT COUNT(*), SUM(pesos) FROM silver_bolton")).one()
        if n != len(df):
            raise RuntimeError(f"silver_bolton: archivo={len(df)} tabla={n}")
        suma_csv = pd.to_numeric(df["pesos"]).sum()
        if abs(float(total) - suma_csv) > 1:
            raise RuntimeError(f"silver_bolton: suma pesos archivo={suma_csv} tabla={total}")
        log.info("silver_bolton cargado desde archivo: %d filas", n)

                # --- silver_integrado.csv -> silver_integrado ---
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS silver_integrado"))
            conn.execute(text("""
                CREATE TABLE silver_integrado (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    anio SMALLINT,
                    mes TINYINT,
                    cliente VARCHAR(255),
                    canal VARCHAR(100),
                    vendedor VARCHAR(150),
                    region VARCHAR(100),
                    zona VARCHAR(100),
                    producto VARCHAR(255),
                    referencia VARCHAR(255),
                    marca VARCHAR(100),
                    familia VARCHAR(100),
                    categoria VARCHAR(100),
                    gr DECIMAL(10,2),
                    cajas DECIMAL(12,2),
                    cajas_valida BOOLEAN,
                    pesos DOUBLE,
                    departamentos VARCHAR(255),
                    n_departamentos TINYINT,
                    poblacion_total BIGINT
                ) CHARACTER SET utf8mb4
            """))

        integrado_file = silver_dir / files["integrado_silver"]
        if not integrado_file.exists():
            raise FileNotFoundError(f"No existe {integrado_file}")

        df = pd.read_csv(integrado_file, encoding="utf-8")
        df = df.astype(object).where(df.notna(), None)   # NaN -> NULL

        df.to_sql("silver_integrado", engine, if_exists="append",
                  index=False, chunksize=5000, method="multi")

        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX idx_si_anio_mes ON silver_integrado (anio, mes)"))
            conn.execute(text("CREATE INDEX idx_si_region ON silver_integrado (region)"))
            conn.execute(text("CREATE INDEX idx_si_marca ON silver_integrado (marca)"))

        # Verificar: conteo, suma de pesos y filas sin departamento
        with engine.connect() as conn:
            n, total, sin_depto = conn.execute(text(
                "SELECT COUNT(*), SUM(pesos), SUM(departamentos IS NULL) "
                "FROM silver_integrado")).one()
        if n != len(df):
            raise RuntimeError(f"silver_integrado: archivo={len(df)} tabla={n}")
        suma_csv = pd.to_numeric(df["pesos"]).sum()
        if abs(float(total) - suma_csv) > 1:
            raise RuntimeError(f"silver_integrado: suma pesos archivo={suma_csv} tabla={total}")
        log.info("silver_integrado cargado desde archivo: %d filas (sin departamento: %s)",
                 n, sin_depto)

    def gold():
        inf = cfg["informes"]

        def leer(nombre_archivo):
            ruta = gold_dir / nombre_archivo
            if not ruta.exists():
                raise FileNotFoundError(f"No existe {ruta}")
            df = pd.read_csv(ruta, encoding="utf-8")
            return df.astype(object).where(df.notna(), None)   # NaN -> NULL

        # ---------- gold_final ----------
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS gold_final"))
            conn.execute(text("""
                CREATE TABLE gold_final (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    anio SMALLINT, mes TINYINT,
                    cliente VARCHAR(255), canal VARCHAR(100), vendedor VARCHAR(150),
                    region VARCHAR(100), zona VARCHAR(100),
                    producto VARCHAR(255), referencia VARCHAR(255),
                    marca VARCHAR(100), familia VARCHAR(100), categoria VARCHAR(100),
                    gr DECIMAL(10,2), cajas DECIMAL(12,2),
                    cajas_valida BOOLEAN, pesos DOUBLE,
                    departamentos VARCHAR(255),
                    n_departamentos TINYINT,
                    poblacion_total BIGINT,
                    cuatrimestre TINYINT,
                    periodo_cuatrimestre VARCHAR(10)
                ) CHARACTER SET utf8mb4
            """))
        df = leer(files["gold"])
        df.to_sql("gold_final", engine, if_exists="append",
                  index=False, chunksize=5000, method="multi")
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX idx_gf_anio_mes ON gold_final (anio, mes)"))
            conn.execute(text("CREATE INDEX idx_gf_periodo ON gold_final (periodo_cuatrimestre)"))
            conn.execute(text("CREATE INDEX idx_gf_region ON gold_final (region)"))
            conn.execute(text("CREATE INDEX idx_gf_marca ON gold_final (marca)"))
        with engine.connect() as conn:
            n, total_final = conn.execute(
                text("SELECT COUNT(*), SUM(pesos) FROM gold_final")).one()
        if n != len(df):
            raise RuntimeError(f"gold_final: archivo={len(df)} tabla={n}")
        suma_csv = pd.to_numeric(df["pesos"]).sum()
        if abs(float(total_final) - suma_csv) > 1:
            raise RuntimeError(f"gold_final: pesos archivo={suma_csv} tabla={total_final}")
        log.info("gold_final cargado desde archivo: %d filas", n)

        # ---------- informes: una tabla por informe ----------
        for clave in INFORMES:
            tabla = f"gold_{clave}"
            df = leer(inf[clave])

            desconocidas = [c for c in df.columns if c not in COL_TYPES]
            if desconocidas:
                raise ValueError(f"{tabla}: columnas sin tipo definido: {desconocidas}")

            col_defs = ", ".join(f"`{c}` {COL_TYPES[c]}" for c in df.columns)
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS `{tabla}`"))
                conn.execute(text(f"CREATE TABLE `{tabla}` ({col_defs}) "
                                  "CHARACTER SET utf8mb4"))
            df.to_sql(tabla, engine, if_exists="append",
                      index=False, chunksize=500, method="multi")

            with engine.connect() as conn:
                n = conn.execute(text(f"SELECT COUNT(*) FROM `{tabla}`")).scalar()
                if clave == "por_anio":
                    total_anual = conn.execute(
                        text("SELECT SUM(pesos) FROM gold_por_anio")).scalar()
            if n != len(df):
                raise RuntimeError(f"{tabla}: archivo={len(df)} tabla={n}")
            if clave == "por_anio" and abs(float(total_anual) - float(total_final)) > 1:
                raise RuntimeError(f"gold_por_anio suma {total_anual} y gold_final {total_final}")
            log.info("%s cargado desde archivo: %d filas", tabla, n)

    bronze()
    silver()
    gold()