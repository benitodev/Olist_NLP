import os
from pathlib import Path

import pandas as pd
import psycopg

from src.db.conn import get_db_conninfo


def run():
    # Paths
    base_dir = Path(__file__).resolve().parents[2]
    raw_dir = Path(os.getenv("RAW_DIR", base_dir / "data" / "raw"))

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
            cur.execute("TRUNCATE TABLE interactions, items;")
            cur.executemany(
                "INSERT INTO items(item_id, category_pt, category_en) VALUES (%s,%s,%s)",
                items.to_records(index=False).tolist(),
            )
        conn.commit()

    print("OK: items loaded into Postgres.")


if __name__ == "__main__":
    run()
