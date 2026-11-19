import unicodedata
from datetime import datetime
from pathlib import Path
import pandas as pd
import yaml

def clean_excel(config_path="config/config.yaml") -> pd.DataFrame:
    # 1 cargar configuración 
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    
    #rutas
    ruta_entrada = Path(cfg["paths"]["bronze"]) / cfg["files"]["bolton_bronze"]
    ruta_salida = Path(cfg["paths"]["silver"]) / cfg["files"]["bolton_silver"]

    print("Proceso de transformación Silver (Bolton)")
    mensajes = []

    # 2 leer bronce
    df_bronze = pd.read_excel(ruta_entrada, dtype=str, keep_default_na=False)

    meses = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
             "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}#asignamos valor  para armar cuatrimestres facilmente
    cols_originales = list(df_bronze.columns)

    # 1. Vacíos y espacios nulo
    df = df_bronze.replace(r"^\s*$", pd.NA, regex=True)

    # 2. pesos acepta 844128.0 y $ 1.101.848,82
    s = df["PESOS"].astype(str).str.strip()
    limpio = (s.str.replace(r"[\$\s]", "", regex=True)
               .str.replace(".", "", regex=False)
               .str.replace(",", ".", regex=False))
    pesos = pd.to_numeric(s, errors="coerce").fillna(pd.to_numeric(limpio, errors="coerce"))
    anio = pd.to_numeric(df["AÑO"], errors="coerce")
    mes = df["MES"].astype(str).str.strip().str.title().map(meses)

    cliente_norm = (df["Nombre Cliente"].astype("string").str.upper().str.strip()#normalizo nombres
                    .map(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
                         if pd.notna(x) else x))

    # 3. Filas que se eliminan
    eliminar = pd.Series(False, index=df.index)
    reglas = [
        ("sin PESOS (forecast, inventario, líneas vacías)", df["PESOS"].isna()),
        ("PESOS no convertible a número", pesos.isna()),
        ("traslado interno (COLOMBOESPAÑOLA)", cliente_norm.str.contains("COLOMBOESPANOLA", na=False)),
        ("devoluciones (FACTURA (-) o PESOS < 0)", (df["DOCUMENTO"].astype(str).str.strip() == "FACTURA (-)") | (pesos < 0)),
        ("PESOS = 0", pesos == 0),
        ("sep-dic 2026 (periodo incompleto)", (anio == 2026) & (mes >= 9)),
    ]
    for nombre, mascara in reglas:
        nuevo = mascara.fillna(False) & ~eliminar
        eliminar = eliminar | nuevo
        mensajes.append(f"Eliminadas por {nombre}: {int(nuevo.sum()):,}")#gaurda los mensajes del log

    # duplicados exactos despues del primer filtro, se usa factura para no confundir
    dup = df.loc[~eliminar, cols_originales].duplicated(keep="first")#solo son duplicados con la misma factura
    dup = dup.reindex(df.index, fill_value=False) & df["Factura"].notna()
    eliminar = eliminar | dup
    mensajes.append(f"Eliminadas por duplicado exacto con factura: {int(dup.sum()):,}")

    v = df.loc[~eliminar].copy()

    # Cálculo de n_repeticiones requerido al final
    claves = v[cols_originales].astype(str).assign(_x=1)
    v["n_repeticiones"] = claves.groupby(cols_originales, sort=False, dropna=False)["_x"].transform("size")

    # 5. Columnas finales
    v["anio"] = anio[v.index].astype("Int64")
    v["mes"] = mes[v.index].astype("Int64")
    v["gr"] = pd.to_numeric(v["GR"], errors="coerce")
    v["cajas"] = pd.to_numeric(v["CAJAS"], errors="coerce")
    v["cajas_valida"] = v["cajas"] > 0
    v["pesos"] = pesos[v.index]

    v = v.rename(columns={"Nombre Cliente": "cliente", "Canal": "canal", "Vendedor": "vendedor",
                          "Ciudad": "region", "Zona": "zona", "Producto": "producto",
                          "Referencia": "referencia", "Marca": "marca", "Familia": "familia",
                          "Categoria": "categoria"})

    # 6. estandarizar
    for col, vacio in [("producto", "SIN CLASIFICAR"), ("referencia", "SIN CLASIFICAR"),
                       ("marca", "SIN CLASIFICAR"), ("familia", "SIN CLASIFICAR"),
                       ("categoria", "SIN CLASIFICAR"), ("cliente", "SIN ASIGNAR"),
                       ("canal", "SIN ASIGNAR"), ("vendedor", "SIN ASIGNAR"),
                       ("region", "SIN ASIGNAR"), ("zona", "SIN ASIGNAR")]:
        v[col] = (v[col].astype("string").str.upper().str.strip().str.replace(r"\s+", " ", regex=True)
                  .map(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
                       if pd.notna(x) else x)
                  .fillna(vacio))

    ventas = v[["anio", "mes", "cliente", "canal", "vendedor", "region", "zona",
                "producto", "referencia", "marca", "familia", "categoria", "gr",
                "cajas", "cajas_valida", "pesos"]].reset_index(drop=True)

    # 8. Guardar y log
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    ventas.to_csv(ruta_salida, index=False, encoding="utf-8")
    mensajes.append(f"Guardado en {ruta_salida}")

    Path("logs").mkdir(exist_ok=True)
    with open("logs/logs.txt", "a", encoding="utf-8") as log_file:
        for m in mensajes:
            print(m)
            log_file.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}; {m}\n")

    return ventas