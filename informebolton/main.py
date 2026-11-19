import logging
import os
from pathlib import Path

from src.extract.extract_api import extract_api
from src.extract.extract_excel import  extraer_bolton
from src.transform.clean_api import clean_api
from src.transform.clean_excel import clean_excel
from src.transform.integrate_silver import integrar_silver
from src.transform.build_gold import build_gold, generar_informes


from src.load.load_database import  load

def main():
    os.chdir(Path(__file__).resolve().parent)
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
                  logging.StreamHandler()],
    )

    extract_api()
    extraer_bolton()
    clean_api()
    clean_excel()
    integrar_silver()
    build_gold()
    generar_informes()
    load()

if __name__ == "__main__":
    main()