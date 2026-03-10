import os
from pathlib import Path

import pandas as pd
import psycopg

from src.db.conn import get_db_conninfo


def run():
    # Paths
    base_dir = Path(__file__).resolve().parents[2]
    raw_dir = Path(os.getenv("RAW_DIR", base_dir / "data" / "raw"))

    orders_path = raw_dir / "olist_orders_dataset.csv"
    order_items_path = raw_dir / "olist_order_items_dataset.csv"
    customers_path = raw_dir / "olist_customers_dataset.csv"

    for p in [orders_path, order_items_path, customers_path]:
        if not p.exists():
            raise FileNotFoundError(f"Missing file: {p}")

    # Load
    orders = pd.read_csv(orders_path, parse_dates=["order_purchase_timestamp"])
    order_items = pd.read_csv(order_items_path)
    customers = pd.read_csv(customers_path)

    # Use delivered orders only (represents completed purchases)
    orders = orders[orders["order_status"] == "delivered"].copy()

    # Join orders -> customers to get customer_unique_id (user_id)
    orders = orders.merge(
        customers[["customer_id", "customer_unique_id"]],
        on="customer_id",
        how="inner",
    )

    # Join orders -> order_items to get product_id (item_id)
    df = orders[["order_id", "customer_unique_id", "order_purchase_timestamp"]].merge(
        order_items[["order_id", "product_id"]],
        on="order_id",
        how="inner",
    )

    df = df.rename(
        columns={
            "customer_unique_id": "user_id",
            "product_id": "item_id",
            "order_purchase_timestamp": "ts",
        }
    )

    df["event_type"] = "purchase"

    # Basic cleanup
    df = (
        df[["user_id", "item_id", "order_id", "ts", "event_type"]]
        .dropna(subset=["user_id", "item_id", "ts"])
        .drop_duplicates(["user_id", "item_id", "ts"])
        .copy()
    )

    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts"])
    print("Interactions rows:", df.shape[0])
    print("Unique users      :", df["user_id"].nunique())
    print("Unique items      :", df["item_id"].nunique())
    print("Min/Max ts        :", df["ts"].min(), df["ts"].max())

    # Load to Postgres (reproducible load: TRUNCATE + INSERT)
    conninfo = get_db_conninfo()
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE interactions;")
            rows = list(df.itertuples(index=False, name=None))
            cur.executemany(
                """
                INSERT INTO interactions(user_id, item_id, order_id, ts, event_type)
                VALUES (%s,%s,%s,%s,%s)
                """,
                rows,
            )
        conn.commit()

    print("OK: interactions loaded into Postgres.")


if __name__ == "__main__":
    run()
