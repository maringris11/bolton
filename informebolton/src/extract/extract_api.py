import csv
import json
import logging
from pathlib import Path

import requests
import yaml

log = logging.getLogger(__name__)


def extract_api(config_path="config/config.yaml"):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    url = f"{cfg['api']['base_url']}/{cfg['api']['endpoint_areas']}"

    r = requests.get(url, timeout=cfg["api"]["timeout"])
    r.raise_for_status()          # si la api falla el pipeline se detiene
    data = r.json()

    out = (Path(cfg["paths"]["bronze"]) / cfg["files"]["areas_bronze"]).with_suffix(".csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(dict.fromkeys(key for row in data for key in row))
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
            for row in data
        )

    log.info("API: %s registros guardados en %s", len(data), out)
    return out