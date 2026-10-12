"""SQLite connection handling, schema setup and settings helpers."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db():
    """Return the per-request connection (created lazily)."""
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(app):
    """Create tables and, on first run, load demo data."""
    from seed import seed_demo_data

    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed_demo_data(db)
            db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    init_db(app)


# Settings that the browser may read (last_bill_no is internal).
PUBLIC_SETTINGS = (
    "restaurant_name", "address", "gstin", "currency",
    "tax_percent", "service_percent", "bill_prefix",
)


def get_settings(db):
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}
