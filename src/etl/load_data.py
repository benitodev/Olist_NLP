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
DB_HOST = os.getenv("POSTGRES_HOST")

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = BASE_DIR / "data" / "raw"

if not DATA_RAW_DIR.exists():
    raise FileNotFoundError(f"Path not found: {DATA_RAW_DIR}")

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

print("Starting ETL load process...")

for csv_file, table_name in csv_to_load.items():
    full_path = DATA_RAW_DIR / csv_file
    print(full_path)

    if full_path.exists():
        print(f"--> Processing {csv_file}...")

        # EXTRACT
        df = pd.read_csv(full_path)

        # TRANSFORM (light cleaning)
        # Convert columns to datetime when the column name contains "timestamp" or "date"
        for col in df.columns:
            if "timestamp" in col.lower() or "date" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # 3) LOAD
        df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=1000)

        print(f"✅ Table '{table_name}' loaded successfully ({len(df)} rows).")
    else:
        print(f"❌ ERROR: File not found: {full_path}. Check the filename.")

print("Data warehouse is ready.")
