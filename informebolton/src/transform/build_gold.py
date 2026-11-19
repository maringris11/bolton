from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml


def _log(mensajes):
    """Imprime y escribe en logs/logs.txt una lista de mensajes."""
    Path("logs").mkdir(exist_ok=True)
    with open("logs/logs.txt", "a", encoding="utf-8") as log_file:
        for m in mensajes:
            print(m)
            log_file.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}; {m}\n")


def build_gold(config_path="config/config.yaml") -> pd.DataFrame:
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    ruta_entrada = Path(cfg["paths"]["silver"]) / cfg["files"]["integrado_silver"]
    ruta_salida = Path(cfg["paths"]["gold"]) / cfg["files"]["gold"]

    gold = pd.read_csv(ruta_entrada)

    # Cuatrimestre
    gold["cuatrimestre"] = (gold["mes"] - 1) // 4 + 1
    gold["periodo_cuatrimestre"] = gold["anio"].astype(str) + "-C" + gold["cuatrimestre"].astype(str)

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    gold.to_csv(ruta_salida, index=False, encoding="utf-8")

    _log([f"Gold generado: {len(gold):,} filas, {gold.shape[1]} columnas -> {ruta_salida}"])
    return gold


def _validar_poblacion(gold):
    """Cada región debe tener una única población; si no, el per cápita sería incorrecto."""
    inconsistentes = (gold.groupby("region", dropna=False)["poblacion_total"]
                          .nunique().loc[lambda s: s > 1])
    if not inconsistentes.empty:
        raise ValueError(f"Regiones con más de una población: {list(inconsistentes.index)}")


def _top_por_anio(gold, columnas, top_n):
    """Suma pesos y cajas por año + columnas, y deja las top_n de cada año."""
    agg = (gold.groupby(["anio"] + columnas, as_index=False, dropna=False)
               .agg(pesos=("pesos", "sum"), cajas=("cajas", "sum")))
    agg = agg.sort_values(["anio", "pesos"], ascending=[True, False])
    agg["ranking"] = agg.groupby("anio")["pesos"].rank(method="first", ascending=False).astype(int)
    return agg[agg["ranking"] <= top_n].reset_index(drop=True)


def _top_per_capita(gold, columnas, top_n, min_pesos=0):
    claves = ["anio"] + columnas

    # Sin columnas repetidas 
    cols_pob = list(dict.fromkeys(claves + ["region", "poblacion_total"]))

    pob = (gold[cols_pob]
               .drop_duplicates()
               .groupby(claves, as_index=False, dropna=False)
               .agg(poblacion=("poblacion_total", "sum")))

    agg = (gold.groupby(claves, as_index=False, dropna=False)
               .agg(pesos=("pesos", "sum"),
                    cajas=("cajas", "sum"),
                    meses_con_datos=("mes", "nunique")))

    agg = agg.merge(pob, on=claves, how="left", validate="1:1")
    agg = agg[agg["pesos"] >= min_pesos]
    agg["pesos_per_capita"] = agg["pesos"] / agg["poblacion"]
    agg["cajas_per_capita"] = agg["cajas"] / agg["poblacion"]

    agg = agg.sort_values(["anio", "pesos_per_capita"], ascending=[True, False])
    agg["ranking"] = (agg.groupby("anio")["pesos_per_capita"]
                         .rank(method="first", ascending=False).astype(int))
    return agg[agg["ranking"] <= top_n].reset_index(drop=True)

def _top_por_grupo(gold, grupo, columna, top_n=1):
    """Top n de columna dentro de cada combinación de grupo, con su participación en el grupo."""
    agg = (gold.groupby(grupo + [columna], as_index=False, dropna=False)
               .agg(pesos=("pesos", "sum"),
                    cajas=("cajas", "sum"),
                    meses_con_datos=("mes", "nunique")))

    # Participación sobre el total real del grupo, calculada antes de recortar al top
    agg["participacion_pesos"] = agg["pesos"] / agg.groupby(grupo)["pesos"].transform("sum")

    agg = agg.sort_values(grupo + ["pesos"], ascending=[True] * len(grupo) + [False])
    agg["ranking"] = agg.groupby(grupo)["pesos"].rank(method="first", ascending=False).astype(int)
    return agg[agg["ranking"] <= top_n].reset_index(drop=True)

def _top_por_cuatrimestre(gold, columna, top_n):
    """Top N de `columna` por cuatrimestre, con su participación sobre el total del período."""
    claves = ["anio", "cuatrimestre", "periodo_cuatrimestre"]

    agg = (gold.groupby(claves + [columna], as_index=False, dropna=False)
               .agg(pesos=("pesos", "sum"),
                    cajas=("cajas", "sum"),
                    meses_con_datos=("mes", "nunique")))

    # Participación calculada ANTES de recortar al top, para que sea sobre el total real del período
    agg["participacion_pesos"] = agg["pesos"] / agg.groupby(claves)["pesos"].transform("sum")

    agg = agg.sort_values(claves[:2] + ["pesos"], ascending=[True, True, False])
    agg["ranking"] = (agg.groupby(claves)["pesos"]
                         .rank(method="first", ascending=False).astype(int))
    return agg[agg["ranking"] <= top_n].reset_index(drop=True)

def generar_informes(config_path="config/config.yaml") -> dict:
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    carpeta_gold = Path(cfg["paths"]["gold"])
    inf = cfg["informes"]
    top_n = inf["top_n"]
    min_pesos = inf.get("min_pesos_per_capita", 0)
    top_n_cuatri = inf.get("top_n_cuatrimestre", 5)
    top_n_marca = inf.get("top_n_marca", 1)

    gold = pd.read_csv(carpeta_gold / cfg["files"]["gold"])
    _validar_poblacion(gold)

    con_vendedor = gold[gold["vendedor"] != "SIN ASIGNAR"]

    informes = {
        # 1. Ventas por año 2026 incompleto
        "por_anio": (gold.groupby("anio", as_index=False)
                         .agg(pesos=("pesos", "sum"), cajas=("cajas", "sum"),
                              n_registros=("pesos", "size"), meses_con_datos=("mes", "nunique"))),
        # 2. Ventas por cuatrimestre
        "por_cuatrimestre": (gold.groupby(["anio", "cuatrimestre", "periodo_cuatrimestre"], as_index=False)
                                 .agg(pesos=("pesos", "sum"), cajas=("cajas", "sum"),
                                      n_registros=("pesos", "size"), meses_con_datos=("mes", "nunique"))),
        # 3. Top regiones
        "top_ciudades": _top_por_anio(gold, ["region", "departamentos"], top_n),
        # 4. Top productos
        "top_productos": _top_por_anio(gold, ["producto"], top_n),
        # 5. Top vendedores (se excluyen los SIN ASIGNAR)
        "top_vendedores": _top_por_anio(con_vendedor, ["vendedor"], top_n),
        # 6. Top ventas per cápita por territorio
        "top_ventas_per_capita": _top_per_capita(gold, ["region", "departamentos"], top_n, min_pesos),
        # 7. Top vendedores per cápita (se excluyen los SIN ASIGNAR)
        "top_vendedores_per_capita": _top_per_capita(con_vendedor, ["vendedor"], top_n, min_pesos),
        # 8 a 11. Top por cuatrimestre para cada nivel de producto
        "top_productos_cuatrimestre":   _top_por_cuatrimestre(gold, "producto", top_n_cuatri),

        "top_referencias_cuatrimestre": _top_por_cuatrimestre(gold, "referencia", top_n_cuatri),

        "top_familias_cuatrimestre":    _top_por_cuatrimestre(gold, "familia", top_n_cuatri),

        "top_categorias_cuatrimestre":  _top_por_cuatrimestre(gold, "categoria", top_n_cuatri),
        # 12. Marca más vendida por región en cada cuatrimestre
        "top_marca_region_cuatrimestre": _top_por_grupo(
            gold, ["anio", "cuatrimestre", "periodo_cuatrimestre", "region"], "marca", top_n_marca),
        # 13. Marca más vendida por región en cada año
        "top_marca_region_anio": _top_por_grupo(
            gold, ["anio", "region"], "marca", top_n_marca),
        
    }

    mensajes = []
    for nombre, df in informes.items():
        ruta = carpeta_gold / inf[nombre]
        df.to_csv(ruta, index=False, encoding="utf-8")
        mensajes.append(f"Informe {nombre}: {len(df):,} filas -> {ruta}")
    _log(mensajes)

    return informes