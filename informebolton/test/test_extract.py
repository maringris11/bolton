"""
test_extract.py
Verifica la integridad de los datos extraídos (bronze) sin usar pytest.
Se ejecuta directamente: python tests/test_extract.py
"""

import pandas as pd
from pathlib import Path
import yaml
import sys
import logging

log = logging.getLogger(__name__)

# Resuelve la raíz del proyecto igual que en src/extract.py
# tests/test_extract.py -> parents[1] = raíz del proyecto (informebolton)
ROOT = Path(__file__).resolve().parents[1]   # AJUSTA el índice si mueves este archivo de carpeta


def cargar_config():
    with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_api_areas_existe_y_tiene_datos(cfg):
    """Caso de prueba + límite: el CSV de la API debe existir y no estar vacío."""
    ruta = ROOT / cfg["paths"]["bronze"] / cfg["files"]["areas_bronze"]

    assert ruta.exists(), f"No existe el archivo {ruta}"

    df = pd.read_csv(ruta, dtype=str)

    assert len(df) > 0, "El archivo de áreas está vacío"
    assert "id" in df.columns or "nombre" in df.columns, "Faltan columnas clave en áreas"

    print(f"[OK] areas_bronze: {len(df)} filas, {df.shape[1]} columnas")
    return True


def test_bolton_existe_y_tiene_datos(cfg):
    """Caso de prueba + límite: el Excel de Bolton debe existir y no estar vacío."""
    ruta = ROOT / cfg["paths"]["bronze"] / cfg["files"]["bolton_bronze"]

    assert ruta.exists(), f"No existe el archivo {ruta}"

    df = pd.read_excel(ruta, dtype=str, keep_default_na=False)

    assert len(df) > 0, "El archivo de Bolton está vacío"

    print(f"[OK] bolton_bronze: {len(df)} filas, {df.shape[1]} columnas")
    return True




def test_integracion_areas_y_bolton_consistentes(cfg):
    """Prueba de integración: ambos archivos de bronze deben poder leerse juntos sin error."""
    ruta_areas = ROOT / cfg["paths"]["bronze"] / cfg["files"]["areas_bronze"]
    ruta_bolton = ROOT / cfg["paths"]["bronze"] / cfg["files"]["bolton_bronze"]

    df_areas = pd.read_csv(ruta_areas, dtype=str)
    df_bolton = pd.read_excel(ruta_bolton, dtype=str, keep_default_na=False)

    assert len(df_areas) > 0 and len(df_bolton) > 0, "Uno de los dos archivos llegó vacío"

    print(f"[OK] Integración: areas ({len(df_areas)} filas) y bolton ({len(df_bolton)} filas) cargan sin error")
    return True


def main():
    cfg = cargar_config()
    tests = [
        test_api_areas_existe_y_tiene_datos,
        test_bolton_existe_y_tiene_datos,
        test_integracion_areas_y_bolton_consistentes,
    ]

    resultados = []
    for test in tests:
        try:
            test(cfg)
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