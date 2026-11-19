import os
import socket
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import streamlit as st
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Ruta raíz de informebolton/ (dos niveles arriba de dashboard/src/db.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
load_dotenv(PROJECT_ROOT / ".env")

def _resolve_host(configured_host: str) -> str:
    """Si config.yaml tiene host.docker.internal pero corremos fuera de Docker, usa 127.0.0.1."""
    env_host = os.getenv("BOLTON_DB_HOST")
    if env_host:
        return env_host
    if configured_host == "host.docker.internal":
        try:
            socket.gethostbyname("host.docker.internal")
            return configured_host
        except socket.gaierror:
            return "127.0.0.1"
    return configured_host


@st.cache_resource
def get_engine():
    """Crea y cachea el engine SQLAlchemy conectado a la base MySQL `bolton`."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db = cfg["database"]
    host = _resolve_host(db["host"])

    url = URL.create(
        drivername=db.get("driver", "mysql+pymysql"),
        username=os.getenv("DB_USER", db.get("user")),
        password=os.getenv("DB_PASSWORD", db.get("password")),
        host=host,
        port=int(os.getenv("BOLTON_DB_PORT", db["port"])),
        database=os.getenv("BOLTON_DB_NAME", db["name"]),
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


@st.cache_data(ttl=600, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Ejecuta una consulta SQL parametrizada contra MySQL y cachea el DataFrame 10 min."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def check_connection() -> tuple[bool, str]:
    """Verifica conectividad y existencia de tablas Gold en MySQL `bolton`."""
    try:
        df = run_query("SELECT COUNT(*) AS filas FROM gold_final")
        filas = int(df["filas"].iloc[0])
        return True, f"Conectado a MySQL `bolton` · {filas:,} registros en `gold_final`"
    except Exception as exc:
        return False, f"Error conectando a MySQL `bolton`: {exc}"