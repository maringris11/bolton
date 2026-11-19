import sys
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import os
from dotenv import load_dotenv

load_dotenv()


ROOT = Path(__file__).resolve().parents[1]  # AJUSTA el índice según dónde quede este archivo


def cargar_config():
    with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["database"]["user"] = os.environ["DB_USER"]
    cfg["database"]["password"] = os.environ["DB_PASSWORD"]
    return cfg


def conectar(cfg):
    db = cfg["database"]
    host = "localhost" if db["host"] == "host.docker.internal" else db["host"]
    engine = create_engine(URL.create(
        drivername=db["driver"], username=db["user"], password=db["password"],
        host=host, port=db["port"], database=db["name"],
        query={"charset": "utf8mb4"},
    ))
    return engine


def test_gold_final_tiene_datos(engine):
    """Caso de prueba: gold_final debe existir y tener filas."""
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM gold_final")).scalar()
    assert n > 0, "gold_final está vacía"
    print(f"[OK] gold_final tiene {n} filas")


def test_gold_final_sin_nulos_en_campos_clave(engine):
    """Prueba de límite: campos obligatorios no deben venir nulos."""
    campos = ["vendedor", "region", "producto", "pesos"]
    with engine.connect() as conn:
        for campo in campos:
            n_nulos = conn.execute(
                text(f"SELECT COUNT(*) FROM gold_final WHERE `{campo}` IS NULL")
            ).scalar()
            assert n_nulos == 0, f"gold_final tiene {n_nulos} filas con '{campo}' nulo"
    print("[OK] Sin nulos en campos clave (vendedor, region, producto, pesos)")


def test_gold_final_sin_valores_negativos(engine):
    """Prueba de límite: no deben existir ventas (pesos) o cajas negativas."""
    with engine.connect() as conn:
        n_pesos_neg = conn.execute(
            text("SELECT COUNT(*) FROM gold_final WHERE pesos < 0")
        ).scalar()
        n_cajas_neg = conn.execute(
            text("SELECT COUNT(*) FROM gold_final WHERE cajas < 0")
        ).scalar()
    assert n_pesos_neg == 0, f"Hay {n_pesos_neg} filas con pesos negativos"
    assert n_cajas_neg == 0, f"Hay {n_cajas_neg} filas con cajas negativas"
    print("[OK] No hay valores negativos en pesos ni cajas")


def test_reconciliacion_gold_final_vs_por_anio(engine):
    """Prueba de integración/reconciliación: la suma de pesos debe
    cuadrar entre gold_final y el informe agregado gold_por_anio."""
    with engine.connect() as conn:
        total_final = conn.execute(text("SELECT SUM(pesos) FROM gold_final")).scalar()
        total_anual = conn.execute(text("SELECT SUM(pesos) FROM gold_por_anio")).scalar()

    diferencia = abs(float(total_final) - float(total_anual))
    assert diferencia <= 1, (
        f"Descuadre entre gold_final ({total_final}) y gold_por_anio ({total_anual}), "
        f"diferencia={diferencia}"
    )
    print(f"[OK] Reconciliación correcta: gold_final={total_final:,.2f} "
          f"≈ gold_por_anio={total_anual:,.2f}")


def main():
    cfg = cargar_config()
    engine = conectar(cfg)

    tests = [
        test_gold_final_tiene_datos,
        test_gold_final_sin_nulos_en_campos_clave,
        test_gold_final_sin_valores_negativos,
        test_reconciliacion_gold_final_vs_por_anio,
    ]

    resultados = []
    for test in tests:
        try:
            test(engine)
            resultados.append((test.__name__, "PASÓ", ""))
        except AssertionError as e:
            resultados.append((test.__name__, "FALLÓ", str(e)))
            print(f"[FALLÓ] {test.__name__}: {e}")
        except Exception as e:
            resultados.append((test.__name__, "ERROR", str(e)))
            print(f"[ERROR] {test.__name__}: {e}")

    print("\n--- Resumen ---")
    for nombre, estado, detalle in resultados:
        print(f"{estado:6} | {nombre} {('- ' + detalle) if detalle else ''}")

    if any(r[1] != "PASÓ" for r in resultados):
        sys.exit(1)


if __name__ == "__main__":
    main()