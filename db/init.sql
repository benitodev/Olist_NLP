CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    category_pt TEXT,
    category_en TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interactions (
    user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    order_id TEXT,
    ts TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'purchase',
    PRIMARY KEY (user_id, item_id, ts)
);

CREATE TABLE IF NOT EXISTS recommendations_users (
    user_id TEXT NOT NULL,
    model TEXT NOT NULL,
    recs JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, model)
);

CREATE TABLE IF NOT EXISTS recommendations_items (
    item_id TEXT NOT NULL,
    model TEXT NOT NULL,
    recs JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (item_id, model)
);

CREATE TABLE IF NOT EXISTS recommendations_context (
    context_type TEXT NOT NULL,
    context_value TEXT NOT NULL,
    model TEXT NOT NULL,
    recs JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (context_type, context_value, model)
);

CREATE TABLE IF NOT EXISTS metrics (
    model TEXT NOT NULL,
    protocol TEXT NOT NULL,
    split_name TEXT NOT NULL,
    k INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- FK: interactions.item_id should exists in items.item_id
ALTER TABLE interactions
  ADD CONSTRAINT fk_interactions_item
  FOREIGN KEY (item_id) REFERENCES items(item_id);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_interactions_user_ts
  ON interactions(user_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_interactions_item_ts
  ON interactions(item_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_lookup
  ON metrics(model, protocol, split_name, metric_name, k);