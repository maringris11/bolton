from datetime import datetime
from pathlib import Path
import pandas as pd
import yaml

def extraer_bolton(config_path="config/config.yaml") -> pd.DataFrame:
    # Cargar configuración
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    
    # Construir la ruta usando bronze y el archivo bolton_bronze del YAML
    ruta = Path(cfg["paths"]["bronze"]) / cfg["files"]["bolton_bronze"]
    
    # Configuración de logs usando la ruta del YAML
    log_dir = Path(cfg["paths"]["logs"])
    log_dir.mkdir(exist_ok=True)
    
    with open(log_dir / "logs.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}; Extrayendo datos de Bolton\n")

    print(f"Proceso de extracción de datos desde: {ruta}")
    
    df_extraccion = pd.read_excel(ruta, dtype=str, keep_default_na=False)
    df_extraccion.columns = [c.strip() for c in df_extraccion.columns]

    print(f"Filas: {len(df_extraccion):,} | Columnas: {df_extraccion.shape[1]}")
    return df_extraccion