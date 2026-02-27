# Olist RecSys API (Serving)

FastAPI service that **serves recommendations from PostgreSQL (Docker)**.

- **Offline (ETL)** builds recommendation artifacts and writes them into Postgres (`recommendations_items`, optionally `recommendations_context`).
- **Online (API / serving)** reads those artifacts and returns JSON responses for a frontend.

---

## Project layout 

```
src/
  api/
    app.py
    README.md
  db/
    conn.py
  etl/
    build_item_item_cooc.py
db/
  init.sql
```

---

## Prerequisites

### 1) PostgreSQL running in Docker
Make sure Postgres is running and port `5432` is exposed to your host (common setup: `5432:5432`).

Check:
```bash
docker ps
```

If you use Docker Compose:
```bash
docker compose up -d
```

> If your container uses a different host/port (or you run Postgres inside Docker network only), update `.env` accordingly.

### 2) Conda environment (Python 3.10)
Activate your conda environment:

```bash
conda activate olist_project
```

Install dependencies **inside the active env**:

```bash
python -m pip install fastapi uvicorn[standard] python-dotenv
python -m pip install "psycopg[binary]"   # psycopg v3 (recommended)
```

If you already have `psycopg` installed without extras, that’s fine too:
```bash
python -m pip install psycopg
```

### 3) Environment variables (`.env`)
The API reads DB connection settings via `src/db/conn.py` (`get_db_conninfo()`).

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
POSTGRES_DB=olist_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

---

## Build artifacts first (ETL)

The API expects `recommendations_items` to be populated (item-to-item neighbors).

Run the ETL job (from project root):

```bash
python -m src.etl.build_item_item_cooc
```

> Tip: if you want to test without writing, use `run(write=False)` from a notebook; for serving you want `write=True` at least once.

Quick Python check (no psql required):

```python
import psycopg
from src.db.conn import get_db_conninfo

with psycopg.connect(get_db_conninfo()) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM recommendations_items;")
        print("rows:", cur.fetchone()[0])
```

---

## Run the API

From the project root:

```bash
python -m uvicorn src.api.app:app --reload
```

Open Swagger UI:
- http://127.0.0.1:8000/docs

---

## Serving logic (important)

### `/recs/item/{item_id}`
For a given `item_id`, the API tries:

1. **Item-to-item co-occurrence neighbors** from `recommendations_items`.
2. If missing: **category popularity** (counts purchases within the same category).
3. If item/category is unknown: **global popularity** (counts purchases overall).

This guarantees **coverage** even when co-occurrence is sparse.

---

## Endpoints

### Health
- **GET** `/ok`

Example:
```bash
curl http://127.0.0.1:8000/ok
```

---

### Item-to-item recommendations (with fallback)
- **GET** `/recs/item/{item_id}`
- **Query params**
  - `k` (int, default `10`, `1 ≤ k ≤ 100`)
  - `model` (optional, string; if omitted, returns the most recent model for that item)

Examples:
```bash
curl "http://127.0.0.1:8000/recs/item/005030ef108f58b46b78116f754d8d38?k=10"
curl "http://127.0.0.1:8000/recs/item/005030ef108f58b46b78116f754d8d38?k=10&model=cooc_cosine_mincooc2_top30"
```

Example response (co-occurrence):
```json
{
  "seed_item_id": "005030ef108f58b46b78116f754d8d38",
  "strategy": "item_item_cooc",
  "model": "cooc_cosine_mincooc2_top30",
  "k": 10,
  "recs": [
    {"item_id": "51250f90d798d377a1928e8a4e2e9ae1", "score": 0.6667, "cooc": 2},
    {"item_id": "75c06ee06b201f9b6301d2b5e72993f8", "score": 0.6667, "cooc": 2}
  ]
}
```

Example response (fallback: category popularity):
```json
{
  "seed_item_id": "some_item_without_neighbors",
  "strategy": "fallback_category_popularity",
  "category": "perfumery",
  "k": 10,
  "recs": [
    {"item_id": "a1b2c3...", "cnt": 120},
    {"item_id": "d4e5f6...", "cnt": 115}
  ]
}
```

Example response (fallback: global popularity):
```json
{
  "seed_item_id": "unknown_item",
  "strategy": "fallback_global_popularity",
  "k": 10,
  "recs": [
    {"item_id": "x1y2z3...", "cnt": 5000},
    {"item_id": "u7v8w9...", "cnt": 4980}
  ]
}
```

---

### Global popularity (Home / Trending)
- **GET** `/recs/popular`
- **Query params**
  - `k` (int, default `10`, `1 ≤ k ≤ 100`)

Example:
```bash
curl "http://127.0.0.1:8000/recs/popular?k=20"
```

---

### Category popularity (Category page)
- **GET** `/recs/popular/category/{category}`
- **Query params**
  - `k` (int, default `10`, `1 ≤ k ≤ 100`)

Example:
```bash
curl "http://127.0.0.1:8000/recs/popular/category/perfumery?k=20"
```

---

### Available models
- **GET** `/recs/models`
- **Query params**
  - `limit` (int, default `50`, `1 ≤ limit ≤ 500`)

Lists models stored in `recommendations_items` with item coverage and latest generation timestamp.

Example:
```bash
curl "http://127.0.0.1:8000/recs/models?limit=20"
```

---

### Available categories (EN/PT)
- **GET** `/recs/popular/categories`
- **Query params**
  - `limit` (int, default `10`, `1 ≤ limit ≤ 100`)

Returns categories from `items` with item counts and both English/Portuguese names (if present as `category_en`, `category_pt`).

Example:
```bash
curl "http://127.0.0.1:8000/recs/popular/categories?limit=50"
```

---

## Troubleshooting

### `psycopg.OperationalError: could not connect to server`
- Ensure Docker container is running: `docker ps`
- Confirm `.env` host/port match your setup (`DB_HOST`, `DB_PORT`)
- If Postgres runs inside Docker Compose with a different port mapping, update `DB_PORT`.

### 422 validation error on `k` / `limit`
This means query params violate constraints (`ge`, `le`), e.g. `k=0` or `k=999`.

### No item-to-item results
If `/recs/item/{item_id}` always falls back:
- run ETL (with `write=True`)
- verify table has rows:
  - `SELECT COUNT(*) FROM recommendations_items;`

---

## Notes (portfolio-friendly)

- The item-to-item model is **intentionally sparse** because the dataset has few multi-item orders.
- Serving uses **fallback strategies** to maintain coverage (category/global popularity).
- This API is implemented with a simple “connect-per-request” pattern (OK for demo). A production variant would add pooling/caching.
