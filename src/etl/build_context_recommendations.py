"""
build_context_recommendations.py

Builds non-personalized, context-based recommendation lists (popularity baselines)
and stores them in Postgres.

It generates:
  1) Global Top-K items by purchase count.
  2) Per-category Top-K items by purchase count (category_en from items table).

IMPORTANT (anti-leakage):
Popularity is computed only from interactions before a cutoff timestamp (TRAIN window):
  interactions.ts < cutoff_ts

Cutoff can be provided via env var CUTOFF_TS. If missing, the script computes it as
the CUTOFF_QUANTILE percentile (0.80) of interactions.ts.

Output table:
  recommendations_context(context_type, context_value, model, recs, generated_at)

Where `recs` is a JSON list:
  [{"item_id": "...", "score": 123.0}, ...]
"""

import json
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd
import psycopg
from dotenv import load_dotenv

from src.db.conn import get_db_conninfo


def build_recs_list(df: pd.DataFrame, k: int) -> List[Dict]:
    """
    Takes a dataframe with columns ['item_id', 'score'] and returns Top-K JSON list.
    """
    df = df.sort_values("score", ascending=False).head(k)
    return [
        {"item_id": str(i), "score": float(s)}
        for i, s in zip(df["item_id"], df["score"])
    ]


def ensure_table_recommendations_context(conn: psycopg.Connection) -> None:
    """
    Creates recommendations_context if it does not exist.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS recommendations_context (
      context_type  text NOT NULL,
      context_value text NOT NULL,
      model         text NOT NULL,
      recs          jsonb NOT NULL,
      generated_at  timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (context_type, context_value, model)
    );
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def get_cutoff_ts(conn: psycopg.Connection) -> str:
    """
    Returns cutoff timestamp as ISO string.

    Priority:
      1) Use env CUTOFF_TS if provided (recommended for reproducibility).
      2) Else compute percentile from purchase interactions.ts using
         CUTOFF_QUANTILE (default 0.80).
    """
    cutoff_env = os.getenv("CUTOFF_TS")
    if cutoff_env and cutoff_env.strip():
        return cutoff_env.strip()

    q = float(os.getenv("CUTOFF_QUANTILE", "0.80"))
    if not (0.0 < q < 1.0):
        raise ValueError("CUTOFF_QUANTILE must be between 0 and 1 (exclusive).")

    sql = """
        SELECT percentile_disc(%s) WITHIN GROUP (ORDER BY ts) AS cutoff_ts
        FROM interactions
        WHERE event_type = 'purchase';
        """
    with conn.cursor() as cur:
        cur.execute(sql, (q,))
        row = cur.fetchone()

    if row is None or row[0] is None:
        raise RuntimeError(
            "Could not compute cutoff timestamp from purchase interactions.ts."
        )

    return str(row[0])


def fetch_popularity(
    conn: psycopg.Connection, cutoff_ts: str, window_days: Optional[int] = None
) -> pd.DataFrame:
    """
    Fetch popularity counts from Postgres, filtered to TRAIN window:
      ts < cutoff_ts
      AND event_type = 'purchase'

    Optional:
      if window_days is provided, also applies:
      ts >= cutoff_ts - interval '{window_days} days'
    (useful for 'trending' style popularity within train).
    """
    params: Tuple = (cutoff_ts,)
    where_clause = """
    WHERE event_type = 'purchase'
      AND ts < CAST(%s AS timestamptz)
    """

    if window_days is not None and window_days > 0:
        where_clause += """
          AND ts >= (CAST(%s AS timestamptz) - make_interval(days => %s))
        """
        params = (cutoff_ts, cutoff_ts, window_days)

    sql = f"""
    SELECT item_id, COUNT(*)::bigint AS score
    FROM interactions
    {where_clause}
    GROUP BY item_id;
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return pd.DataFrame(rows, columns=["item_id", "score"])


def fetch_items(conn: psycopg.Connection) -> pd.DataFrame:
    """
    Fetch item metadata needed for context recommendations.
    """
    sql = "SELECT item_id, category_en FROM items;"
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["item_id", "category_en"])


def upsert_recommendations(
    conn: psycopg.Connection,
    rows_to_upsert: List[Tuple[str, str, str, str]],
) -> None:
    """
    Upsert rows into recommendations_context.

    Each row tuple is:
      (context_type, context_value, model, recs_json)
    """
    sql = """
    INSERT INTO recommendations_context(context_type, context_value, model, recs, generated_at)
    VALUES (%s, %s, %s, %s::jsonb, now())
    ON CONFLICT (context_type, context_value, model)
    DO UPDATE SET recs = EXCLUDED.recs,
                  generated_at = EXCLUDED.generated_at;
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows_to_upsert)
    conn.commit()


def run():
    load_dotenv()

    topk = int(os.getenv("TOPK", "30"))
    if topk <= 0:
        raise ValueError("TOPK must be > 0")

    model_name = os.getenv("MODEL_NAME", "popularity_context")

    # Optional trending-style restriction within train window (days before cutoff)
    window_days_env = os.getenv("WINDOW_DAYS", "").strip()
    window_days = int(window_days_env) if window_days_env else None

    conninfo = get_db_conninfo()

    with psycopg.connect(conninfo) as conn:
        ensure_table_recommendations_context(conn)

        cutoff_ts = get_cutoff_ts(conn)
        print(f"[build_context_recommendations] cutoff_ts = {cutoff_ts}")

        pop = fetch_popularity(conn, cutoff_ts=cutoff_ts, window_days=window_days)
        if pop.empty:
            raise RuntimeError(
                "Popularity query returned 0 rows. Check interactions table and cutoff/window."
            )

        items = fetch_items(conn)

        # Global top-K
        global_recs = build_recs_list(pop, topk)

        # Category top-K (join popularity with category metadata)
        pop_cat = pop.merge(items, on="item_id", how="left")
        pop_cat["category_en"] = pop_cat["category_en"].astype("string")
        pop_cat["category_en"] = (
            pop_cat["category_en"].fillna("unknown").replace("NaN", "unknown")
        )

        rows_to_upsert: List[Tuple[str, str, str, str]] = []

        # 1) global/all
        rows_to_upsert.append(("global", "all", model_name, json.dumps(global_recs)))

        # 2) per category_en
        for cat, grp in pop_cat.groupby("category_en"):
            recs = build_recs_list(grp[["item_id", "score"]], topk)
            rows_to_upsert.append(
                ("category_en", str(cat), model_name, json.dumps(recs))
            )

        print(
            f"[build_context_recommendations] Prepared rows: {len(rows_to_upsert)} (global + categories)"
        )

        upsert_recommendations(conn, rows_to_upsert)

    print("[build_context_recommendations] OK: recommendations_context updated.")


if __name__ == "__main__":
    run()
