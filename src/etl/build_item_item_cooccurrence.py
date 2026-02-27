import json
from itertools import combinations

import numpy as np
import pandas as pd
import psycopg

from src.db.conn import get_db_conninfo


def compute_cutoff_ts(conn, cutoff_quantile: float):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT percentile_disc(%s) WITHIN GROUP (ORDER BY ts) AS cutoff_ts
            FROM interactions
            WHERE event_type='purchase';
            """,
            (cutoff_quantile,),
        )
        return cur.fetchone()[0]


def fetch_train_orders(conn, cutoff_ts):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT order_id::text, item_id::text
            FROM interactions
            WHERE event_type='purchase'
              AND ts < %s
              AND order_id IS NOT NULL;
            """,
            (cutoff_ts,),
        )
        rows = cur.fetchall()
    return pd.DataFrame.from_records(rows, columns=["order_id", "item_id"])


def basket_summary(df_train_orders: pd.DataFrame) -> pd.Series:
    order_sizes = df_train_orders.groupby("order_id")["item_id"].nunique()
    return pd.Series(
        {
            "n_orders_total": float(order_sizes.shape[0]),
            "n_orders_1_item": float((order_sizes == 1).sum()),
            "n_orders_2plus": float((order_sizes >= 2).sum()),
            "pct_orders_1_item": float((order_sizes == 1).mean()),
            "pct_orders_2plus": float((order_sizes >= 2).mean()),
            "avg_items_per_order": float(order_sizes.mean()),
        }
    )


def fetch_items_cat(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute("SELECT item_id::text, category_en::text FROM items;")
        items_rows = cur.fetchall()

    items_cat = pd.DataFrame(items_rows, columns=["item_id", "category_en"])
    items_cat["category_en"] = (
        items_cat["category_en"].astype("string").fillna("unknown")
    )
    return items_cat


def build_item2cat(items_cat: pd.DataFrame) -> dict:
    return dict(
        zip(items_cat["item_id"].astype(str), items_cat["category_en"].astype(str))
    )


def build_pairs_and_scores(df_train_orders: pd.DataFrame):
    order_items = df_train_orders.groupby("order_id")["item_id"].apply(
        lambda x: list(pd.unique(x))
    )
    order_items = order_items[order_items.apply(len) >= 2]

    item_freq = pd.Series([it for lst in order_items for it in lst]).value_counts()

    pair_counts = {}
    for lst in order_items:
        lst = sorted(lst)
        for a, b in combinations(lst, 2):
            pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    pairs = pd.DataFrame(
        [(a, b, c) for (a, b), c in pair_counts.items()],
        columns=["item_a", "item_b", "cooc"],
    )

    pairs["freq_a"] = pairs["item_a"].map(item_freq)
    pairs["freq_b"] = pairs["item_b"].map(item_freq)
    pairs["score"] = pairs["cooc"] / np.sqrt(pairs["freq_a"] * pairs["freq_b"])

    meta = {
        "orders_with_2plus": int(len(order_items)),
        "pairs_total": int(len(pairs)),
    }
    return pairs, meta


def build_neighbors(
    pairs: pd.DataFrame, items_cat: pd.DataFrame, min_cooc: int, topk: int
):
    pairs_f = pairs[pairs["cooc"] >= min_cooc].copy()

    edges = pd.concat(
        [
            pairs_f.rename(columns={"item_a": "item_id", "item_b": "neighbor_item_id"})[
                ["item_id", "neighbor_item_id", "score", "cooc"]
            ],
            pairs_f.rename(columns={"item_b": "item_id", "item_a": "neighbor_item_id"})[
                ["item_id", "neighbor_item_id", "score", "cooc"]
            ],
        ],
        ignore_index=True,
    )

    edges = edges.sort_values(
        ["item_id", "score", "cooc"], ascending=[True, False, False]
    )
    edges["rank"] = edges.groupby("item_id").cumcount() + 1
    neighbors_cooc = edges[edges["rank"] <= topk].copy()

    n_catalog = items_cat["item_id"].nunique()
    coverage = neighbors_cooc["item_id"].nunique() / max(n_catalog, 1)

    meta = {
        "pairs_after_min_cooc": int(len(pairs_f)),
        "neighbors_rows": int(len(neighbors_cooc)),
        "items_with_neighbors": int(neighbors_cooc["item_id"].nunique()),
        "catalog_items": int(n_catalog),
        "coverage": float(coverage),
    }
    return neighbors_cooc, meta


def compute_same_cat_rate(
    neighbors_cooc: pd.DataFrame, items_cat: pd.DataFrame, topn: int = 10
) -> float:
    nb = neighbors_cooc.merge(items_cat, on="item_id", how="left").rename(
        columns={"category_en": "cat_item"}
    )
    nb = nb.merge(
        items_cat,
        left_on="neighbor_item_id",
        right_on="item_id",
        how="left",
        suffixes=("", "_nb"),
    )
    nb = nb.rename(columns={"category_en": "cat_nb"}).drop(columns=["item_id_nb"])

    top = nb[nb["rank"] <= topn].copy()
    return float((top["cat_item"] == top["cat_nb"]).mean())


def prepare_rows_to_upsert(neighbors_cooc: pd.DataFrame, model_name: str):
    rows_to_upsert = []
    for item_id, grp in neighbors_cooc.groupby("item_id"):
        grp = grp.sort_values("rank")
        recs = [
            {"item_id": str(nb), "score": float(sc), "cooc": int(co)}
            for nb, sc, co in zip(grp["neighbor_item_id"], grp["score"], grp["cooc"])
        ]
        rows_to_upsert.append((str(item_id), model_name, json.dumps(recs)))
    return rows_to_upsert


def ensure_table_recommendations_items(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS recommendations_items (
      item_id      text NOT NULL,
      model        text NOT NULL,
      recs         jsonb NOT NULL,
      generated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (item_id, model)
    );
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def upsert_item_recs_chunked(conn, rows, batch_size=500):
    sql = """
    INSERT INTO recommendations_items(item_id, model, recs, generated_at)
    VALUES (%s, %s, %s::jsonb, now())
    ON CONFLICT (item_id, model)
    DO UPDATE SET recs = EXCLUDED.recs,
                  generated_at = EXCLUDED.generated_at;
    """
    with conn.cursor() as cur:
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            cur.executemany(sql, chunk)
            conn.commit()


def run(cutoff_quantile=0.80, min_cooc=2, topk=30, write=False):
    conninfo = get_db_conninfo()
    model_name = f"cooc_cosine_mincooc{min_cooc}_top{topk}"

    with psycopg.connect(conninfo) as conn:
        cutoff_ts = compute_cutoff_ts(conn, cutoff_quantile)

        df_train_orders = fetch_train_orders(conn, cutoff_ts)
        summary = basket_summary(df_train_orders)

        items_cat = fetch_items_cat(conn)
        item2cat = build_item2cat(items_cat)

        pairs, pairs_meta = build_pairs_and_scores(df_train_orders)
        neighbors_cooc, neighbors_meta = build_neighbors(
            pairs, items_cat, min_cooc=min_cooc, topk=topk
        )

        same_cat_rate_top10 = compute_same_cat_rate(neighbors_cooc, items_cat, topn=10)

        if write:
            rows_to_upsert = prepare_rows_to_upsert(neighbors_cooc, model_name)
            ensure_table_recommendations_items(conn)
            upsert_item_recs_chunked(conn, rows_to_upsert, batch_size=500)

    return {
        "model_name": model_name,
        "cutoff_ts": cutoff_ts,
        "basket_summary": summary,
        "items_cat": items_cat,
        "item2cat": item2cat,
        "pairs_meta": pairs_meta,
        "neighbors_cooc": neighbors_cooc,
        "neighbors_meta": neighbors_meta,
        "same_cat_rate_top10": same_cat_rate_top10,
    }


if __name__ == "__main__":
    out = run(write=True)
    print("model_name:", out["model_name"])
    print("same_cat_rate_top10:", out["same_cat_rate_top10"])
    print("coverage:", out["neighbors_meta"]["coverage"])
