-- Restaurant Billing & Management System: SQLite schema.
-- All money is stored as integer paise (1 rupee = 100 paise) to avoid floating-point errors.
-- Tax / service / percent-discount rates are stored as basis points (5% = 500).

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name          TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin', 'cashier')),
  active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS categories (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
  sort_order INTEGER NOT NULL DEFAULT 0
);

-- Menu items are soft-deleted (active = 0) so past orders keep working.
CREATE TABLE IF NOT EXISTS menu_items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  name         TEXT NOT NULL,
  price        INTEGER NOT NULL CHECK (price >= 0),
  is_veg       INTEGER NOT NULL DEFAULT 1,
  is_available INTEGER NOT NULL DEFAULT 1,
  active       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id);

CREATE TABLE IF NOT EXISTS dining_tables (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  name   TEXT NOT NULL UNIQUE COLLATE NOCASE,
  seats  INTEGER NOT NULL DEFAULT 4 CHECK (seats > 0),
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  table_id        INTEGER REFERENCES dining_tables(id),
  order_type      TEXT NOT NULL DEFAULT 'dine_in' CHECK (order_type IN ('dine_in', 'takeaway')),
  customer_name   TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid', 'cancelled')),
  discount_type   TEXT NOT NULL DEFAULT 'none' CHECK (discount_type IN ('none', 'percent', 'flat')),
  discount_value  INTEGER NOT NULL DEFAULT 0 CHECK (discount_value >= 0), -- basis points or paise
  tax_bp          INTEGER NOT NULL DEFAULT 0,
  service_bp      INTEGER NOT NULL DEFAULT 0,
  subtotal        INTEGER NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  tax_amount      INTEGER NOT NULL DEFAULT 0,
  service_amount  INTEGER NOT NULL DEFAULT 0,
  round_off       INTEGER NOT NULL DEFAULT 0,
  total           INTEGER NOT NULL DEFAULT 0,
  bill_no         TEXT UNIQUE,
  payment_method  TEXT CHECK (payment_method IN ('cash', 'card', 'upi')),
  amount_paid     INTEGER,
  change_due      INTEGER,
  cancel_reason   TEXT,
  created_by      INTEGER REFERENCES users(id),
  created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  paid_at         TEXT
);
-- The database itself guarantees a table can never have two open orders.
CREATE UNIQUE INDEX IF NOT EXISTS uq_open_order_per_table
  ON orders(table_id) WHERE status = 'open' AND table_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_paid_at ON orders(paid_at);

-- Name and price are copied onto the line so later menu edits never change old bills.
CREATE TABLE IF NOT EXISTS order_items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
  name         TEXT NOT NULL,
  unit_price   INTEGER NOT NULL CHECK (unit_price >= 0),
  qty          INTEGER NOT NULL CHECK (qty > 0),
  notes        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
