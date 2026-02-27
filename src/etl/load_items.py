import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


def get_db_conninfo() -> str:
    """
    Builds a psycopg connection string using your .env variables:
      POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    and optional DB_HOST/DB_PORT (defaults: localhost:5432).
    """
    load_dotenv()
    dbname = os.getenv("POSTGRES_DB", "olist_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def main():
    # Paths
    project_root = Path(__file__).resolve().parents[2]
    raw_dir = Path(os.getenv("RAW_DIR", project_root / "data" / "raw"))

    products_path = raw_dir / "olist_products_dataset.csv"
    cat_tr_path = raw_dir / "product_category_name_translation.csv"

    if not products_path.exists():
        raise FileNotFoundError(f"Missing file: {products_path}")
    if not cat_tr_path.exists():
        raise FileNotFoundError(f"Missing file: {cat_tr_path}")

    # Load CSVs
    products = pd.read_csv(products_path)
    translation = pd.read_csv(cat_tr_path)

    # Merge to get English category names
    df = products.merge(translation, on="product_category_name", how="left")

    # Build items catalog
    items = (
        df.rename(
            columns={
                "product_id": "item_id",
                "product_category_name": "category_pt",
                "product_category_name_english": "category_en",
            }
        )[["item_id", "category_pt", "category_en"]]
        .drop_duplicates("item_id")
        .dropna(subset=["item_id"])
        .copy()
    )

    print("Prepared items:", items.shape)

    # Load into Postgres (reproducible load: TRUNCATE + INSERT)
    conninfo = get_db_conninfo()
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE items;")
            cur.executemany(
                "INSERT INTO items(item_id, category_pt, category_en) VALUES (%s,%s,%s)",
                items.to_records(index=False).tolist(),
            )
        conn.commit()

    print("OK: items loaded into Postgres.")


if __name__ == "__main__":
    main()
