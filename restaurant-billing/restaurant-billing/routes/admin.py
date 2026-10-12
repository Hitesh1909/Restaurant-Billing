"""Menu, categories, dining tables and restaurant settings."""
import re
import sqlite3

from flask import Blueprint, jsonify

from db import PUBLIC_SETTINGS, get_db, get_settings
from routes.auth import login_required
from utils import ApiError, as_int, clean_str, json_body, percent_to_bp

bp = Blueprint("admin", __name__, url_prefix="/api")


# ---------------------------------------------------------------- menu (read)
@bp.get("/menu")
@login_required()
def menu():
    db = get_db()
    categories = [dict(r) for r in db.execute(
        "SELECT id, name, sort_order FROM categories ORDER BY sort_order, name")]
    items = [dict(r) for r in db.execute(
        """SELECT i.id, i.name, i.category_id, c.name AS category_name,
                  i.price, i.is_veg, i.is_available
           FROM menu_items i LEFT JOIN categories c ON c.id = i.category_id
           WHERE i.active = 1
           ORDER BY c.sort_order, c.name, i.name""")]
    return jsonify(categories=categories, items=items)


# ----------------------------------------------------------------- categories
@bp.post("/categories")
@login_required("admin")
def create_category():
    data = json_body()
    name = clean_str(data.get("name"), "Category name", 40, required=True)
    db = get_db()
    next_order = db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories").fetchone()[0]
    try:
        db.execute("INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, next_order))
        db.commit()
    except sqlite3.IntegrityError:
        raise ApiError(f'A category named "{name}" already exists.', 409)
    return jsonify(ok=True), 201


@bp.put("/categories/<int:category_id>")
@login_required("admin")
def rename_category(category_id):
    name = clean_str(json_body().get("name"), "Category name", 40, required=True)
    db = get_db()
    try:
        cur = db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        db.commit()
    except sqlite3.IntegrityError:
        raise ApiError(f'A category named "{name}" already exists.', 409)
    if cur.rowcount == 0:
        raise ApiError("Category not found.", 404)
    return jsonify(ok=True)


@bp.delete("/categories/<int:category_id>")
@login_required("admin")
def delete_category(category_id):
    db = get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM menu_items WHERE category_id = ? AND active = 1", (category_id,)
    ).fetchone()[0]
    if count:
        raise ApiError(f"Move or delete the {count} item(s) in this category first.", 409)
    cur = db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    if cur.rowcount == 0:
        raise ApiError("Category not found.", 404)
    return jsonify(ok=True)


# ----------------------------------------------------------------- menu items
def _validated_item(db, data, item_id=None):
    name = clean_str(data.get("name"), "Item name", 80, required=True)
    category_id = as_int(data.get("category_id"), "Category", 1)
    if not db.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone():
        raise ApiError("Category not found.", 404)
    price = as_int(data.get("price"), "Price", 0, 10_000_000)  # paise
    duplicate = db.execute(
        """SELECT 1 FROM menu_items
           WHERE active = 1 AND category_id = ? AND name = ? COLLATE NOCASE AND id IS NOT ?""",
        (category_id, name, item_id)).fetchone()
    if duplicate:
        raise ApiError(f'"{name}" already exists in this category.', 409)
    return (name, category_id, price,
            int(bool(data.get("is_veg", True))), int(bool(data.get("is_available", True))))


@bp.post("/menu-items")
@login_required("admin")
def create_item():
    db = get_db()
    values = _validated_item(db, json_body())
    db.execute(
        "INSERT INTO menu_items (name, category_id, price, is_veg, is_available) VALUES (?,?,?,?,?)",
        values)
    db.commit()
    return jsonify(ok=True), 201


@bp.put("/menu-items/<int:item_id>")
@login_required("admin")
def update_item(item_id):
    db = get_db()
    existing = db.execute("SELECT * FROM menu_items WHERE id = ? AND active = 1", (item_id,)).fetchone()
    if existing is None:
        raise ApiError("Menu item not found.", 404)
    merged = {**dict(existing), **json_body()}  # partial updates are fine
    values = _validated_item(db, merged, item_id)
    db.execute(
        """UPDATE menu_items SET name = ?, category_id = ?, price = ?, is_veg = ?, is_available = ?
           WHERE id = ?""", (*values, item_id))
    db.commit()
    return jsonify(ok=True)


@bp.delete("/menu-items/<int:item_id>")
@login_required("admin")
def delete_item(item_id):
    db = get_db()
    cur = db.execute("UPDATE menu_items SET active = 0 WHERE id = ? AND active = 1", (item_id,))
    db.commit()
    if cur.rowcount == 0:
        raise ApiError("Menu item not found.", 404)
    return jsonify(ok=True)


# --------------------------------------------------------------------- tables
def _table_values(data):
    name = clean_str(data.get("name"), "Table name", 20, required=True)
    seats = as_int(data.get("seats", 4), "Seats", 1, 50)
    return name, seats


@bp.post("/tables")
@login_required("admin")
def create_table():
    name, seats = _table_values(json_body())
    db = get_db()
    try:
        db.execute("INSERT INTO dining_tables (name, seats) VALUES (?, ?)", (name, seats))
        db.commit()
    except sqlite3.IntegrityError:
        raise ApiError(f'A table named "{name}" already exists.', 409)
    return jsonify(ok=True), 201


@bp.put("/tables/<int:table_id>")
@login_required("admin")
def update_table(table_id):
    name, seats = _table_values(json_body())
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE dining_tables SET name = ?, seats = ? WHERE id = ? AND active = 1",
            (name, seats, table_id))
        db.commit()
    except sqlite3.IntegrityError:
        raise ApiError(f'A table named "{name}" already exists.', 409)
    if cur.rowcount == 0:
        raise ApiError("Table not found.", 404)
    return jsonify(ok=True)


@bp.delete("/tables/<int:table_id>")
@login_required("admin")
def delete_table(table_id):
    db = get_db()
    if db.execute("SELECT 1 FROM orders WHERE table_id = ? AND status = 'open'", (table_id,)).fetchone():
        raise ApiError("This table has an open order. Bill or cancel it first.", 409)
    # Rename on removal so the name can be reused later (old orders keep the link).
    cur = db.execute(
        "UPDATE dining_tables SET active = 0, name = name || ' (removed ' || id || ')' "
        "WHERE id = ? AND active = 1", (table_id,))
    db.commit()
    if cur.rowcount == 0:
        raise ApiError("Table not found.", 404)
    return jsonify(ok=True)


# ------------------------------------------------------------------- settings
@bp.get("/settings")
@login_required()
def read_settings():
    settings = get_settings(get_db())
    return jsonify({k: settings.get(k, "") for k in PUBLIC_SETTINGS})


@bp.put("/settings")
@login_required("admin")
def update_settings():
    data = json_body()
    prefix = clean_str(data.get("bill_prefix"), "Bill prefix", 8, required=True).upper()
    if not re.fullmatch(r"[A-Z0-9]+", prefix):
        raise ApiError("Bill prefix can only contain letters and numbers.")
    tax_bp = percent_to_bp(data.get("tax_percent"), "Tax %")
    service_bp = percent_to_bp(data.get("service_percent"), "Service charge %")
    values = {
        "restaurant_name": clean_str(data.get("restaurant_name"), "Restaurant name", 80, required=True),
        "address": clean_str(data.get("address"), "Address", 200),
        "gstin": clean_str(data.get("gstin"), "GSTIN", 20),
        "currency": clean_str(data.get("currency"), "Currency symbol", 3, required=True),
        "tax_percent": f"{tax_bp / 100:g}",
        "service_percent": f"{service_bp / 100:g}",
        "bill_prefix": prefix,
    }
    db = get_db()
    db.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", values.items())
    db.commit()
    return jsonify(values)
