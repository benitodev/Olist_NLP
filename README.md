# Olist DS — NLP (Bad Review Detection) and Recommender Systems (Cold/Warm Start)

End-to-end Data Science / ML project built on the **Olist Brazilian E-Commerce Dataset** (Kaggle), with two main modules:

1) **NLP + Classification**: detecting negative reviews (*bad reviews*) from Portuguese text and topic modeling (NMF).  
2) **Recommender Systems**: baselines and models for **cold-start** (new users) and **warm-start** (returning users).

The project also includes a reproducible **data engineering** approach (ETL), and a production-oriented stack with **Postgres + Docker** and **FastAPI** for model serving.

---

## What it solves

- **Automatically detect bad customer experiences** from reviews (to prioritize support/QA).
- **Recommend products** using different strategies depending on user context (new vs returning) and the amount of available history.

---

## Dataset

**Source**: Olist Brazilian E-Commerce Public Dataset (Kaggle)  
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Tables used (from the public dataset):
- Orders, Customers, Products, Sellers, Geolocation
- Reviews (Portuguese text)

---

## Module 1 — NLP: Bad Review Detection

### Target
Definition used:

- `bad_review = 1` if `review_score <= 2`
- `bad_review = 0` if `review_score > 2`

### Pipeline (high-level)
- Text cleaning and normalization:
  - lowercasing
  - accent normalization
  - Portuguese stopwords (while preserving negations such as `não`)
- Vectorization:
  - **TF-IDF word n-grams**
  - optional **char n-grams** (helpful for noise/typos)
- Models evaluated (strong, reproducible baselines):
  - Logistic Regression
  - Linear SVM / calibrated variants

### Split & evaluation
- **Time-based split** (to avoid leakage).
- Metrics:
  - ROC-AUC, PR-AUC
  - F1 / Precision / Recall for the minority class (bad reviews)
  - threshold analysis (*threshold tuning*) according to a business objective

### Results (baseline)
Example (TF-IDF + Logistic Regression):
- **ROC-AUC ≈ 0.95**
- **PR-AUC ≈ 0.82**
- **F1 (bad)** ≈ 0.83
- **Recall (bad)** ≈ 0.91
- Confusion matrix (example): `[[5665, 640], [183, 1641]]`

> Note: exact values may vary slightly depending on seeds, time cutoffs, or text filtering.

---

## Module 2 — Recommender Systems (Cold Start vs Warm Start)

This dataset is highly **sparse** at the user–item level.
With the time split used here, most users have **only 1 purchase** in TRAIN, which limits pure collaborative methods.

### Why separate scenarios
- **Cold-start (new user)**: no history → use popularity/context baselines.
- **Warm-start (returning user)**: some history → try CF / item-item / hybrid approaches.

---

### Scenario A — Cold Start (new users)

#### Baseline 1: Global Popularity
Recommends the global Top-K items by popularity.

Example **HitRate@K** (cold-start):
- K=10 → ~0.0119
- K=50 → ~0.0385
- K=80 → ~0.0600

#### Baseline 2: Category Popularity (contextual)
Simulates a “category page”: given a category context, recommend the Top-K items within that category.

Example **HitRate@K** (cold-start, category popularity):
- K=10 → ~0.1110  
- K=20 → ~0.1676  
- K=50 → ~0.2464  

In cold-start, **category popularity** often outperforms global popularity because it leverages context.

---

### Scenario B — Warm Start (returning users)

#### Warm evaluation
- **Leave-last-out / time-based** split: train on past history and evaluate on the user’s “latest” purchase.

#### Collaborative Filtering (ALS) — warm-focused
- Build a user–item matrix from TRAIN (CSR).
- Train ALS (e.g., `implicit` library or equivalent).

Important observation:
- Sparsity is severe (few users with ≥2 purchases). Example in TRAIN:
  - `>=2` interactions: ~6%
  - `>=3`: ~0.9%
- With so little user history, ALS tends to have low coverage/recall.

Example (ALS product-level HitRate@K):
- K=10 → 0.0
- K=15 → ~0.0238
- K=30 → ~0.0476

Practical takeaway: for this dataset, **pure CF** is not enough on its own; a **hybrid approach with fallbacks** is recommended.

---

### Item-to-Item (Co-occurrence) + “Real neighbors” in Postgres

Build an item–item graph based on co-occurrence in orders (basket analysis):
- Only considers orders with **2+ items**.
- Cosine-style score on counts: `cooc / sqrt(freq_a * freq_b)`
- Store only the “real neighbors” (top-K) in the DB for efficient serving.

Example (from training):
- orders with 2+ items: ~2560
- co-occurring pairs: ~3135
- typical hyperparams: `TOPK=30`, `MIN_COOC=2` (higher precision, lower coverage)

Recommended serving logic:
1) If the query item has neighbors → recommend item-item neighbors.
2) Otherwise → fallback to **category popularity**.
3) If category is missing → fallback to **global popularity**.

---

### NLP Similarity (KNN on texts) — “Issue Similarity”
Extra: TF-IDF + cosine similarity to retrieve similar reviews (useful for):
- clustering recurring issues (customer support)
- debugging product/logistics problems
- exploratory topic/claim analysis

---

## Suggested repository structure

> Adjust names if your repo differs.

```
OLIST_DS/
│
├── data/
│   ├── raw/                # Original Kaggle CSVs
│   ├── processed/          # Clean datasets / features
│   └── README.md
│
├── notebooks/
│   ├── 1_eda_python.ipynb
│   ├── 2_build_dataset.ipynb
│   ├── 3_eda_text_quality.ipynb
│   ├── 4_baseline_text_vs_nontext.ipynb
│   ├── 5_recommender_baseline.ipynb
│   ├── 6_warm_evaluation_split.ipynb
│   ├── 7_issue_similarity_Knn.ipynb
│   ├── 8_colaborative_filtering.ipynb
│   └── 9_item_item_recs_cooccurrence_store_real_neighbors.ipynb
│
├── src/
│   ├── etl/                # Load to Postgres / cleaning
│   ├── nlp/                # training/eval NLP
│   ├── recsys/             # baselines + ALS + item-item
│   └── utils/
│
├── docker-compose.yml      # Postgres (and optional API)
├── .env.example            # env vars (do not commit real .env)
└── README.md
```

---

## Installation & run (reproducible)

### 1) Clone
```bash
git clone https://github.com/<your-user>/<your-repo>.git
cd <your-repo>
```

### 2) Dataset
Download the Kaggle dataset and place the CSVs in:
```text
data/raw/
```

### 3) Environment (Conda)
```bash
conda create -n olist_ds python=3.11 -y
conda activate olist_ds

# if you have requirements.txt
pip install -r requirements.txt
```

### 4) (Optional) Start Postgres with Docker
```bash
docker compose up -d
```

Configure environment variables in `.env` (example):
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

### 5) ETL to Postgres (if applicable)
```bash
python -m src.etl.load_data
```

### 6) Run notebooks
```bash
jupyter lab
```
Open `notebooks/` and run in order (EDA → dataset → NLP baselines → recsys).

---

## Metrics (how to read them)

### Classification
- **ROC-AUC / PR-AUC**: ranking quality, robust with imbalance.
- **F1 / Recall / Precision**: depend on the chosen threshold.

### Recommendation
- **HitRate@K**: equals 1 if at least 1 recommended item is in the user’s ground-truth set; otherwise 0.
  - A simple, clear metric for baselines and cold-start.

---

## Key design decisions

- **Time-based split** to avoid leakage (NLP and RecSys).
- **Cold vs warm** separation due to dataset sparsity.
- Robust serving with **fallbacks** (item-item → category → global).

---

## Roadmap / future improvements

- **FastAPI** service for:
  - `POST /predict_bad_review`
  - `GET /recommend?user_id=...` (warm)
  - `GET /recommend?item_id=...` (item-item)
- Experiment tracking (MLflow) + dataset versioning.
- Transformer models (BERTimbau / multilingual) vs TF-IDF baselines.
- Hybrid recsys (ALS + item-item + content) and/or session-based approaches.
- Additional metrics: MAP@K / NDCG@K (warm), coverage/diversity.

---

