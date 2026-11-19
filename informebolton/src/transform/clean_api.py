from pathlib import Path
import pandas as pd
import yaml
import json

def clean_api(config_path="config/config.yaml"):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    
    # 1. Leer desde Bronze 
    ruta_bronze = Path(cfg["paths"]["bronze"]) / cfg["files"]["areas_bronze"]
    df_bronze = pd.read_csv(ruta_bronze)
    
    # 2. 
    df_silver = pd.DataFrame()
    df_silver["departamento"] = df_bronze["name"].astype(str).str.strip()
    df_silver["superficie"] = pd.to_numeric(df_bronze["surface"], errors="coerce")
    df_silver["poblacion"] = pd.to_numeric(df_bronze["population"], errors="coerce")
    
    def extraer_capital(val):
        if pd.isna(val) or not str(val).strip():
            return None
        try:
            data = json.loads(val) if isinstance(val, str) else val
            return data.get("name")
        except:
            return None

    df_silver["ciudad_capital"] = df_bronze["cityCapital"].apply(extraer_capital)
    df_silver = df_silver.dropna(subset=["departamento"])
    
    # 3. Guardar el resultado en Silver 
    ruta_silver = Path(cfg["paths"]["silver"]) / cfg["files"]["areas_silver"]
    ruta_silver.parent.mkdir(parents=True, exist_ok=True)
    df_silver.to_csv(ruta_silver, index=False, encoding="utf-8")
    
    return df_silver