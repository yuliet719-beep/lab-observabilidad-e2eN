-- Amazon RDS for PostgreSQL (AWS) - base de datos "inventory"
CREATE TABLE IF NOT EXISTS inventory (
  sku    TEXT PRIMARY KEY,
  stock  INT NOT NULL
);
INSERT INTO inventory (sku, stock)
SELECT 'SKU-' || lpad(g::text, 4, '0'), 1000000 FROM generate_series(0, 199) g;
