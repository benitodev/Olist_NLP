from typing import Any, Dict, List, Optional, Tuple

import psycopg
from fastapi import HTTPException, Query

from src.api.app import (
    _normalize_item_id,
    fallback_top_popular_by_category,
    fallback_top_popular_global,
    fetch_item_category,
    fetch_item_neighbors,
    fetch_recent_user_items,
    fetch_user_precomputed_recs,
    most_frequent_category_from_items,
)
from src.db.conn import get_db_conninfo
from src.repositories.recs_repo import fetch_context_recs

CONNINFO = get_db_conninfo()


def aggregate_item_item_recs(
    seed_items: List[str],
    k: int,
    model: Optional[str] = None,
    per_seed_k: int = 50,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Aggregate neighbors from multiple seed items (simple union + rank-by-frequency).
    Returns: (model_name_used, recs_list)
    """
    if not seed_items:
        return None, []

    counts: Dict[str, int] = {}
    model_name_used: Optional[str] = None

    for seed in seed_items:
        m, neigh = fetch_item_neighbors(seed, k=per_seed_k, model=model)
        if m and model_name_used is None:
            model_name_used = m

        for rec in neigh:
            iid = _normalize_item_id(rec)
            if not iid:
                continue
            if iid in seed_items:
                continue
            counts[iid] = counts.get(iid, 0) + 1

    # Sort by how many seeds recommended the item (frequency)
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:k]
    recs_list = [{"item_id": iid, "support": sup} for iid, sup in ranked]
    return model_name_used, recs_list


def recs_for_item(
    item_id: str, k: int = Query(10, ge=1, le=100), model: Optional[str] = Query(None)
):
    model_name, recs = fetch_item_neighbors(item_id=item_id, k=k, model=model)
    if recs:
        return {
            "seed_item_id": item_id,
            "strategy": "item_item_cooc",
            "model": model_name,
            "k": k,
            "recs": recs,
        }

    cat = fetch_item_category(item_id)
    if cat:
        pop = fallback_top_popular_by_category(cat, k=k)
        return {
            "seed_item_id": item_id,
            "strategy": "fallback_category_popularity",
            "category": cat,
            "k": k,
            "recs": pop,
        }

    pop = fallback_top_popular_global(k=k)
    return {
        "seed_item_id": item_id,
        "strategy": "fallback_global_popularity",
        "k": k,
        "recs": pop,
    }


def recs_popular(k: int = Query(10, ge=1, le=100)):
    pop = fallback_top_popular_global(k=k)
    return {"strategy": "fallback_global_popularity", "k": k, "recs": pop}


def recs_popular_by_category(category: str, k: int = Query(10, ge=1, le=100)):
    pop_cat = fallback_top_popular_by_category(category, k=k)
    return {
        "strategy": "category_popularity",
        "category": category,
        "k": k,
        "recs": pop_cat,
    }


def recs_models(limit: int = Query(50, ge=1, le=500)):
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT model,
                       COUNT(*)::int AS n_items,
                       MAX(generated_at) AS latest_generated_at
                FROM recommendations_items
                GROUP BY model
                ORDER BY latest_generated_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return {
        "limit": limit,
        "models": [
            {"model": m, "n_items": n, "latest_generated_at": str(ts)}
            for (m, n, ts) in rows
        ],
    }


def recs_popular_categories(limit: int = Query(10, ge=1, le=100)):
    with psycopg.connect(CONNINFO) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT category_en, category_pt, COUNT(*)::int AS n_items
                from items 
                GROUP BY category_en, category_pt
                ORDER BY n_items DESC LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return {
        "limit": limit,
        "categories": [
            {"category_english": en, "category_portuguese": pt, "n_items": n}
            for (en, pt, n) in rows
        ],
    }


def recs_for_context(
    context_type: str,
    context_value: str,
    k: int = Query(10, ge=1, le=100),
    model: Optional[str] = Query(None),
):
    # 1) Try precomputed context recs
    model_name, recs = fetch_context_recs(context_type, context_value, k=k, model=model)
    if recs:
        return {
            "strategy": "context_precomputed",
            "context_type": context_type,
            "context_value": context_value,
            "model": model_name,
            "k": k,
            "recs": recs,
        }

    # 2) Fallbacks for common contexts
    # Category context -> category popularity (computed on the fly from interactions)
    if context_type.lower() in {"category", "category_en"}:
        pop = fallback_top_popular_by_category(context_value, k=k)
        return {
            "strategy": "fallback_category_popularity",
            "context_type": context_type,
            "context_value": context_value,
            "k": k,
            "recs": pop,
        }

    # Global context -> global popularity
    if context_type.lower() in {"global", "home", "homepage"}:
        pop = fallback_top_popular_global(k=k)
        return {
            "strategy": "fallback_global_popularity",
            "context_type": context_type,
            "context_value": context_value,
            "k": k,
            "recs": pop,
        }

    # Unknown context: return 404 or safe empty response
    raise HTTPException(
        status_code=404,
        detail=f"No recommendations found for context ({context_type}={context_value}).",
    )


def recs_for_user(
    user_id: str,
    k: int = Query(10, ge=1, le=100),
    model: Optional[str] = Query(None),
    history_n: int = Query(5, ge=1, le=50),
):
    # 1) Precomputed user recommendations
    model_name, recs = fetch_user_precomputed_recs(user_id=user_id, k=k, model=model)
    if recs:
        return {
            "strategy": "user_precomputed",
            "user_id": user_id,
            "model": model_name,
            "k": k,
            "recs": recs,
        }

    # 2) If we have user history, build recs from item-item neighbors
    recent_items = fetch_recent_user_items(user_id=user_id, n=history_n)

    if recent_items:
        m_used, agg = aggregate_item_item_recs(
            seed_items=recent_items, k=k, model=model, per_seed_k=max(50, k * 5)
        )
        if agg:
            return {
                "strategy": "user_item_item_aggregate",
                "user_id": user_id,
                "model": m_used,
                "k": k,
                "seed_items": recent_items,
                "recs": agg,
            }

        # 2b) If item-item is missing, fallback to category popularity using user's recent items
        cat = most_frequent_category_from_items(recent_items)
        if cat:
            pop = fallback_top_popular_by_category(cat, k=k)
            return {
                "strategy": "fallback_category_popularity",
                "user_id": user_id,
                "category": cat,
                "k": k,
                "seed_items": recent_items,
                "recs": pop,
            }

    # 3) Cold user (no history) -> global popularity
    pop = fallback_top_popular_global(k=k)
    return {
        "strategy": "fallback_global_popularity",
        "user_id": user_id,
        "k": k,
        "recs": pop,
    }
