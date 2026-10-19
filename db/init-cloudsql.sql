-- Cloud SQL for PostgreSQL (GCP) - base de datos "orders"
CREATE TABLE IF NOT EXISTS orders (
  id          BIGSERIAL PRIMARY KEY,
  customer    TEXT NOT NULL,
  sku         TEXT NOT NULL,
  qty         INT  NOT NULL DEFAULT 1,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO orders (customer, sku, qty)
SELECT 'cliente-' || (g % 500), 'SKU-' || lpad((g % 200)::text, 4, '0'), 1 + (g % 3)
FROM generate_series(1, 5000) g;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
