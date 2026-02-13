import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_PORT = os.getenv("POSTGRES_PORT")
DB_NAME = os.getenv("POSTGRES_DB")
DB_HOST = "localhost"

path = os.path
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = BASE_DIR / "data" / "raw"

if not DATA_RAW_DIR.exists():
    raise FileNotFoundError(f"The path {DATA_RAW_DIR} failed")

conn_string = (
    f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_engine(conn_string)


csv_to_load = {
    "olist_customers_dataset.csv": "customers",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_products_dataset.csv": "products",
    "olist_order_reviews_dataset.csv": "reviews",
    "product_category_name_translation.csv": "category_translation",
}

print("🚀 Iniciando proceso de carga ETL...")

for csv_file, table_name in csv_to_load.items():
    full_path = DATA_RAW_DIR / csv_file
    print(full_path)
    if full_path.exists():
        print(f"--> Procesando {csv_file}...")

        # 1. EXTRACT (Leer)
        df = pd.read_csv(full_path)

        # 2. TRANSFORM (Pequeña limpieza preventiva)
        # Convertimos columnas de fecha automáticamente si el nombre contiene "timestamp"
        # Esto ayuda a que SQL entienda que son fechas y no texto
        for col in df.columns:
            if "timestamp" in col or "date" in col:
                df[col] = pd.to_datetime(df[col])

        # 3. LOAD (Cargar a SQL)
        # if_exists='replace': Si la tabla ya existe, la borra y la crea de nuevo (útil para pruebas)
        # index=False: No guardamos el índice numérico de pandas (0,1,2...)
        df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=1000)

        print(f" Tabla '{table_name}' cargada exitosamente ({len(df)} filas).")
    else:
        print(f" ERROR: No encontré el archivo {full_path}. Verifica el nombre.")

print("¡Proceso finalizado! Tu Data Warehouse está listo.")
