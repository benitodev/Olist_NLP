import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

from src.db.conn import get_sqlalchemy_url

csv_to_load = {
    "olist_customers_dataset.csv": "customers",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_products_dataset.csv": "products",
    "olist_order_reviews_dataset.csv": "reviews",
    "product_category_name_translation.csv": "category_translation",
}


def run():
    load_dotenv()

    base_dir = Path(__file__).resolve().parents[2]
    raw_dir = Path(os.getenv("RAW_DIR", base_dir / "data" / "raw"))

    if not raw_dir.exists():
        raise FileNotFoundError(f"Path not found: {raw_dir}")

    engine = create_engine(get_sqlalchemy_url())

    print("Starting ETL load process...")

    for csv_file, table_name in csv_to_load.items():
        full_path = raw_dir / csv_file
        print(full_path)

        if full_path.exists():
            print(f"--> Processing {csv_file}...")

            df = pd.read_csv(full_path)

            for col in df.columns:
                if "timestamp" in col.lower() or "date" in col.lower():
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            df.to_sql(
                table_name, engine, if_exists="replace", index=False, chunksize=1000
            )

            print(f"✅ Table '{table_name}' loaded successfully ({len(df)} rows).")
        else:
            print(f"❌ ERROR: File not found: {full_path}. Check the filename.")

    print("Data warehouse is ready.")


if __name__ == "__main__":
    run()
