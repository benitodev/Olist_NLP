from typing import Any, Dict, List, Optional, Tuple

import psycopg

from src.db.conn import get_db_conninfo
from src.utils.json_utils import _as_list

CONNINFO = get_db_conninfo()


def fetch_item_neighbors(item_id: str, k: int, model: Optional[str] = None):
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            if model:
                cur.execute(
                    """
                    SELECT model, recs
                    FROM recommendations_items
                    WHERE item_id=%s AND model=%s
                    LIMIT 1;
                    """,
                    (item_id, model),
                )
            else:
                cur.execute(
                    """
                    SELECT model, recs
                    FROM recommendations_items
                    WHERE item_id=%s
                    ORDER BY generated_at DESC
                    LIMIT 1;
                    """,
                    (item_id,),
                )
            row = cur.fetchone()

    if not row:
        return None, []

    model_name, recs = row
    recs_list = _as_list(recs)[:k]
    return model_name, recs_list


def fetch_item_category(item_id: str) -> Optional[str]:
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT category_en FROM items WHERE item_id=%s LIMIT 1;",
                (item_id,),
            )
            row = cur.fetchone()
    return row[0] if row else None


def fallback_top_popular_global(k: int) -> List[Dict[str, Any]]:
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id::text, COUNT(*)::int AS cnt
                FROM interactions
                WHERE event_type='purchase'
                GROUP BY item_id
                ORDER BY cnt DESC
                LIMIT %s;
                """,
                (k,),
            )
            rows = cur.fetchall()
    return [{"item_id": iid, "cnt": cnt} for iid, cnt in rows]


def fallback_top_popular_by_category(category: str, k: int) -> List[Dict[str, Any]]:
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.item_id::text, COUNT(*)::int AS cnt
                FROM interactions x
                JOIN items i ON i.item_id = x.item_id
                WHERE x.event_type='purchase'
                  AND i.category_en=%s
                GROUP BY i.item_id
                ORDER BY cnt DESC
                LIMIT %s;
                """,
                (category, k),
            )
            rows = cur.fetchall()
    return [{"item_id": iid, "cnt": cnt} for iid, cnt in rows]


def fetch_context_recs(
    context_type: str, context_value: str, k: int, model: Optional[str] = None
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Fetch precomputed recs from recommendations_context.
    If model is None, returns the most recently generated model for that context.
    """
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            if model:
                cur.execute(
                    """
                    SELECT model, recs
                    FROM recommendations_context
                    WHERE context_type=%s AND context_value=%s AND model=%s
                    LIMIT 1;
                    """,
                    (context_type, context_value, model),
                )
            else:
                cur.execute(
                    """
                    SELECT model, recs
                    FROM recommendations_context
                    WHERE context_type=%s AND context_value=%s
                    ORDER BY generated_at DESC
                    LIMIT 1;
                    """,
                    (context_type, context_value),
                )
            row = cur.fetchone()

    if not row:
        return None, []

    model_name, recs = row
    recs_list = _as_list(recs)[:k]
    return model_name, recs_list


def fetch_user_precomputed_recs(
    user_id: str, k: int, model: Optional[str] = None
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Fetch precomputed user recs from recommendations_users.
    If model is None, returns the most recently generated model for that user.
    """
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            if model:
                cur.execute(
                    """
                    SELECT model, recs
                    FROM recommendations_users
                    WHERE user_id=%s AND model=%s
                    LIMIT 1;
                    """,
                    (user_id, model),
                )
            else:
                cur.execute(
                    """
                    SELECT model, recs
                    FROM recommendations_users
                    WHERE user_id=%s
                    ORDER BY generated_at DESC
                    LIMIT 1;
                    """,
                    (user_id,),
                )
            row = cur.fetchone()

    if not row:
        return None, []

    model_name, recs = row
    recs_list = _as_list(recs)[:k]
    return model_name, recs_list


def fetch_recent_user_items(user_id: str, n: int = 5) -> List[str]:
    """
    Fetch last N purchased items for a user from interactions.
    """
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id::text
                FROM interactions
                WHERE user_id=%s AND event_type='purchase'
                ORDER BY ts DESC
                LIMIT %s;
                """,
                (user_id, n),
            )
            rows = cur.fetchall()
    return [r[0] for r in rows]
