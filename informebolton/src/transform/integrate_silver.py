import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml


def _norm(x) -> str:
    """MAYÚSCULAS, sin tildes y sin espacios sobrantes (misma regla que clean_excel)."""
    return unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper().strip()


def integrar_silver(config_path="config/config.yaml") -> pd.DataFrame:
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    ruta_silver = Path(cfg["paths"]["silver"])
    mensajes = []

    areas = pd.read_csv(ruta_silver / cfg["files"]["areas_silver"])
    bolton = pd.read_csv(ruta_silver / cfg["files"]["bolton_silver"])
    n_filas, pesos_total = len(bolton), bolton["pesos"].sum()

    # 1. tabla puente región comercial 
    puente = pd.DataFrame(
        [(_norm(region), dep) for region, deps in cfg["mapeo_regiones"].items() for dep in deps],
        columns=["region", "departamento"],
    )
    puente["llave"] = puente["departamento"].map(_norm)
    areas["llave"] = areas["departamento"].map(_norm)

    # 2. Validación: todo departamento del mapeo debe existir en areas.csv
    faltan = set(puente["llave"]) - set(areas["llave"])
    if faltan:
        raise ValueError(f"Departamentos del mapeo que no están en areas.csv: {sorted(faltan)}")

    # 3. Traer población de cada departamento y resumir por región
    puente = puente.merge(areas[["llave", "poblacion"]], on="llave", how="left", validate="m:1")
    regiones = puente.groupby("region", as_index=False).agg(
        departamentos=("departamento", ", ".join),
        n_departamentos=("departamento", "size"),
        poblacion_total=("poblacion", "sum"),
    )

    # 4. Unir con Bolton
    bolton["_llave_region"] = bolton["region"].map(_norm)
    integrado = bolton.merge(regiones, left_on="_llave_region", right_on="region",
                             how="left", suffixes=("", "_mapeo"), validate="m:1")
    integrado = integrado.drop(columns=["_llave_region", "region_mapeo"])

    assert len(integrado) == n_filas, "El merge cambió el número de filas"
    assert abs(integrado["pesos"].sum() - pesos_total) < 1, "El merge cambió el total de pesos"
    sin_match = int(integrado["departamentos"].isna().sum())
    mensajes.append(f"Integrado silver: {len(integrado):,} filas; sin departamento asignado: {sin_match:,}")

    # 6. Guardar y log
    ruta_salida = ruta_silver / cfg["files"]["integrado_silver"]
    integrado.to_csv(ruta_salida, index=False, encoding="utf-8")
    mensajes.append(f"Guardado en {ruta_salida}")

    Path("logs").mkdir(exist_ok=True)
    with open("logs/logs.txt", "a", encoding="utf-8") as log_file:
        for m in mensajes:
            print(m)
            log_file.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}; {m}\n")

    return integrado