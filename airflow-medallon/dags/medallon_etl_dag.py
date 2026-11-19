from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pendulum
from airflow.sdk import DAG, get_current_context, task
from airflow.exceptions import AirflowFailException

PROJECT_DIR = Path("/opt/airflow/informebolton")
os.chdir(PROJECT_DIR)          
sys.path.insert(0, str(PROJECT_DIR))
log = logging.getLogger(__name__)

GOLD_PATH = PROJECT_DIR / "data" / "gold" / "gold_final.csv"
REQUERIDAS = ["anio", "mes", "region", "producto", "marca", "pesos", "cajas",
              "poblacion_total", "cuatrimestre", "periodo_cuatrimestre"]
NO_NEGATIVAS: list[str] = []


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


with DAG(
    dag_id="etl_bolton_hourly",
    description="ETL Medallion: Bronze -> Silver -> Gold -> Validate -> Load. TZ: America/Bogota",
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Bogota"),
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["ETL", "medallion"],
) as dag:

    @task
    def extract_api():
        from src.extract.extract_api import extract_api as fn
        return str(fn())

    @task
    def extract_excel():
        from src.extract.extract_excel import extraer_bolton as fn
        fn()
        return str(PROJECT_DIR / "data" / "bronze" / "bolton.xlsx")
        
    @task
    def validar_bronze(api_path: str, excel_path: str):
        from pathlib import Path
        for p in (api_path, excel_path):
            f = Path(p)
            if not f.exists() or f.stat().st_size == 0:
                raise AirflowFailException(f"Bronze vacío o inexistente: {p}")
        log.info("Bronze OK: %s, %s", api_path, excel_path)
        return "ok"

    @task
    def clean_api(_ok: str):
        from src.transform.clean_api import clean_api as fn
        return str(fn())

    @task
    def clean_excel(_ok: str):
        from src.transform.clean_excel import clean_excel as fn
        return str(fn())

    @task
    def integrate(_a: str, _b: str):
        from src.transform.integrate_silver import integrar_silver
        return str(integrar_silver())

    @task
    def gold(_silver: str):
        from src.transform.build_gold import build_gold
        build_gold()
        return str(GOLD_PATH)

    @task
    def generar_informes(_gold: str):
        from src.transform.build_gold import generar_informes
        generar_informes()
        return "ok"

    @task
    def validate_gold(gold_path: str):
        p = Path(gold_path)
        if not p.exists():
            raise AirflowFailException(f"No existe {p}")

        df = pd.read_csv(p)
        log.info("Gold: %d filas, %d columnas", len(df), df.shape[1])

        if df.empty:
            raise AirflowFailException("Gold vacío")

        faltan = [c for c in REQUERIDAS if c not in df.columns]
        if faltan:
            raise AirflowFailException(f"Faltan columnas: {faltan}")

        for c in ["anio", "mes", "pesos"]:
            n = int(df[c].isna().sum())
            if n:
                raise AirflowFailException(f"{n} nulos en '{c}'")

        if not df["mes"].between(1, 12).all():
            raise AirflowFailException("Hay valores de 'mes' fuera de 1-12")

        num = df.select_dtypes(include="number")
        if np.isinf(num.to_numpy(dtype=float)).any():
            raise AirflowFailException("Hay valores infinitos en columnas numéricas")

        log.info("Gold validado OK: %d filas, pesos=%.2f", len(df), df["pesos"].sum())
        return str(p)

    @task
    def load(_gold: str):
        from src.load.load_database import load as fn
        fn()

    a = extract_api()
    e = extract_excel()
    ok = validar_bronze(a, e)
    ca = clean_api(ok)
    ce = clean_excel(ok)
    i = integrate(ca, ce)
    g = gold(i)
    v = validate_gold(g)
    inf = generar_informes(v)
    load(inf)