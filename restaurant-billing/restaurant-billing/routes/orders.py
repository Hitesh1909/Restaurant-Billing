"""Orders: tables, order lifecycle (open -> paid / cancelled), items, discount and payment."""
import sqlite3

from flask import Blueprint, jsonify, request, session

from billing import compute_totals
from db import get_db, get_settings
from routes.auth import login_required
from utils import ApiError, as_int, clean_str, json_body, percent_to_bp

bp = Blueprint("orders", __name__, url_prefix="/api")

PAYMENT_METHODS = ("cash", "card", "upi")
MAX_QTY = 99


# -------------------------------------------------------------------- helpers
def fetch_order(db, order_id):
    row = db.execute(
        """SELECT o.*, t.name AS table_name, u.name AS cashier
           FROM orders o
           LEFT JOIN dining_tables t ON t.id = o.table_id
           LEFT JOIN users u ON u.id = o.created_by
           WHERE o.id = ?""", (order_id,)).fetchone()
    if row is None:
        raise ApiError("Order not found.", 404)
    order = dict(row)
    order["items"] = [dict(r) for r in db.execute(
        "SELECT id, menu_item_id, name, unit_price, qty, notes FROM order_items "
        "WHERE order_id = ? ORDER BY id", (order_id,))]
    return order


def open_order(db, order_id):
    order = fetch_order(db, order_id)
    if order["status"] != "open":
        raise ApiError(f"This order is already {order['status']} and can't be changed.", 409)
    return order


def recalc(db, order_id):
    """Recompute and store the totals of an open order from its lines and current settings."""
    order = db.execute(
        "SELECT discount_type, discount_value FROM orders WHERE id = ?", (order_id,)).fetchone()
    subtotal = db.execute(
        "SELECT COALESCE(SUM(unit_price * qty), 0) FROM order_items WHERE order_id = ?",
        (order_id,)).fetchone()[0]
    settings = get_settings(db)
    tax_bp = percent_to_bp(settings.get("tax_percent", "0"), "Tax %")
    service_bp = percent_to_bp(settings.get("service_percent", "0"), "Service charge %")
    t = compute_totals(subtotal, order["discount_type"], order["discount_value"], tax_bp, service_bp)
    db.execute(
        """UPDATE orders SET tax_bp = ?, service_bp = ?, subtotal = ?, discount_amount = ?,
                  tax_amount = ?, service_amount = ?, round_off = ?, total = ? WHERE id = ?""",
        (tax_bp, service_bp, t["subtotal"], t["discount_amount"], t["tax_amount"],
         t["service_amount"], t["round_off"], t["total"], order_id))


# --------------------------------------------------------------------- tables
@bp.get("/tables")
@login_required()
def list_tables():
    rows = get_db().execute(
        """SELECT t.id, t.name, t.seats, o.id AS order_id, o.total AS order_total,
                  o.created_at AS order_since,
                  (SELECT COALESCE(SUM(qty), 0) FROM order_items WHERE order_id = o.id) AS item_count
           FROM dining_tables t
           LEFT JOIN orders o ON o.table_id = t.id AND o.status = 'open'
           WHERE t.active = 1 ORDER BY t.id""").fetchall()
    return jsonify([dict(r) for r in rows])


# ----------------------------------------------------------------- order list
@bp.get("/orders")
@login_required()
def list_orders():
    sql = """SELECT o.id, o.bill_no, o.order_type, o.status, o.customer_name, o.total,
                    o.payment_method, o.created_at, o.paid_at, t.name AS table_name,
                    (SELECT COALESCE(SUM(qty), 0) FROM order_items i WHERE i.order_id = o.id) AS item_count
             FROM orders o LEFT JOIN dining_tables t ON t.id = o.table_id WHERE 1 = 1"""
    args = []
    status = request.args.get("status", "")
    if status in ("open", "paid", "cancelled"):
        sql += " AND o.status = ?"
        args.append(status)
    order_type = request.args.get("type", "")
    if order_type in ("dine_in", "takeaway"):
        sql += " AND o.order_type = ?"
        args.append(order_type)
    day = request.args.get("date", "")
    if day:
        sql += " AND date(COALESCE(o.paid_at, o.created_at)) = ?"
        args.append(day)
    q = request.args.get("q", "").strip()
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += (" AND (o.bill_no LIKE ? ESCAPE '\\' OR o.customer_name LIKE ? ESCAPE '\\'"
                " OR t.name LIKE ? ESCAPE '\\' OR CAST(o.id AS TEXT) = ?)")
        args += [like, like, like, q.lstrip("#")]
    sql += " ORDER BY o.id DESC LIMIT 200"
    return jsonify([dict(r) for r in get_db().execute(sql, args)])


# ------------------------------------------------------------- order lifecycle
@bp.post("/orders")
@login_required()
def create_order():
    data = json_body()
    db = get_db()
    order_type = data.get("order_type", "dine_in")
    if order_type not in ("dine_in", "takeaway"):
        raise ApiError("Order type must be dine_in or takeaway.")
    customer = clean_str(data.get("customer_name"), "Customer name", 60)
    table_id = None
    if order_type == "dine_in":
        table_id = as_int(data.get("table_id"), "Table", 1)
        if not db.execute("SELECT 1 FROM dining_tables WHERE id = ? AND active = 1", (table_id,)).fetchone():
            raise ApiError("Table not found.", 404)

    def existing_open():
        return db.execute(
            "SELECT id FROM orders WHERE table_id = ? AND status = 'open'", (table_id,)).fetchone()

    if table_id and existing_open():  # re-use the table's running order
        return jsonify(fetch_order(db, existing_open()["id"]))
    try:
        cur = db.execute(
            "INSERT INTO orders (table_id, order_type, customer_name, created_by) VALUES (?, ?, ?, ?)",
            (table_id, order_type, customer, session["user_id"]))
        recalc(db, cur.lastrowid)
        db.commit()
    except sqlite3.IntegrityError:  # another device opened the table at the same moment
        db.rollback()
        return jsonify(fetch_order(db, existing_open()["id"]))
    return jsonify(fetch_order(db, cur.lastrowid)), 201


@bp.get("/orders/<int:order_id>")
@login_required()
def get_order(order_id):
    return jsonify(fetch_order(get_db(), order_id))


@bp.patch("/orders/<int:order_id>")
@login_required()
def update_order(order_id):
    data = json_body()
    db = get_db()
    open_order(db, order_id)
    if "customer_name" in data:
        db.execute("UPDATE orders SET customer_name = ? WHERE id = ?",
                   (clean_str(data["customer_name"], "Customer name", 60), order_id))
    if "discount_type" in data:
        dtype = data["discount_type"]
        if dtype not in ("none", "percent", "flat"):
            raise ApiError("Discount type must be none, percent or flat.")
        # percent -> basis points (10% = 1000); flat -> paise
        value = 0 if dtype == "none" else as_int(
            data.get("discount_value"), "Discount", 0, 10000 if dtype == "percent" else 100_000_000)
        db.execute("UPDATE orders SET discount_type = ?, discount_value = ? WHERE id = ?",
                   (dtype, value, order_id))
    recalc(db, order_id)
    db.commit()
    return jsonify(fetch_order(db, order_id))


@bp.post("/orders/<int:order_id>/cancel")
@login_required()
def cancel_order(order_id):
    reason = clean_str(json_body().get("reason"), "Reason", 200)
    db = get_db()
    open_order(db, order_id)
    db.execute("UPDATE orders SET status = 'cancelled', cancel_reason = ? WHERE id = ?",
               (reason or "No reason given", order_id))
    db.commit()
    return jsonify(fetch_order(db, order_id))


# ---------------------------------------------------------------- order items
@bp.post("/orders/<int:order_id>/items")
@login_required()
def add_item(order_id):
    data = json_body()
    db = get_db()
    open_order(db, order_id)
    item_id = as_int(data.get("menu_item_id"), "Menu item", 1)
    item = db.execute("SELECT * FROM menu_items WHERE id = ? AND active = 1", (item_id,)).fetchone()
    if item is None:
        raise ApiError("That menu item no longer exists. Refresh the menu.", 404)
    if not item["is_available"]:
        raise ApiError(f"{item['name']} is sold out.", 409)
    qty = as_int(data.get("qty", 1), "Quantity", 1, MAX_QTY)
    notes = clean_str(data.get("notes"), "Note", 200)
    line = db.execute(
        "SELECT id, qty FROM order_items WHERE order_id = ? AND menu_item_id = ? AND notes = ?",
        (order_id, item_id, notes)).fetchone()
    if line:
        if line["qty"] + qty > MAX_QTY:
            raise ApiError(f"You can't add more than {MAX_QTY} of one item.")
        db.execute("UPDATE order_items SET qty = qty + ? WHERE id = ?", (qty, line["id"]))
    else:
        db.execute(
            "INSERT INTO order_items (order_id, menu_item_id, name, unit_price, qty, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)", (order_id, item_id, item["name"], item["price"], qty, notes))
    recalc(db, order_id)
    db.commit()
    return jsonify(fetch_order(db, order_id))


def _line(db, order_id, line_id):
    line = db.execute(
        "SELECT * FROM order_items WHERE id = ? AND order_id = ?", (line_id, order_id)).fetchone()
    if line is None:
        raise ApiError("That item is no longer on this order.", 404)
    return line


@bp.patch("/orders/<int:order_id>/items/<int:line_id>")
@login_required()
def update_item(order_id, line_id):
    data = json_body()
    db = get_db()
    open_order(db, order_id)
    _line(db, order_id, line_id)
    if "qty" in data:
        db.execute("UPDATE order_items SET qty = ? WHERE id = ?",
                   (as_int(data["qty"], "Quantity", 1, MAX_QTY), line_id))
    if "notes" in data:
        db.execute("UPDATE order_items SET notes = ? WHERE id = ?",
                   (clean_str(data["notes"], "Note", 200), line_id))
    recalc(db, order_id)
    db.commit()
    return jsonify(fetch_order(db, order_id))


@bp.delete("/orders/<int:order_id>/items/<int:line_id>")
@login_required()
def remove_item(order_id, line_id):
    db = get_db()
    open_order(db, order_id)
    _line(db, order_id, line_id)
    db.execute("DELETE FROM order_items WHERE id = ?", (line_id,))
    recalc(db, order_id)
    db.commit()
    return jsonify(fetch_order(db, order_id))


# -------------------------------------------------------------------- payment
@bp.post("/orders/<int:order_id>/pay")
@login_required()
def pay_order(order_id):
    data = json_body()
    db = get_db()
    order = open_order(db, order_id)
    if not order["items"]:
        raise ApiError("Add at least one item before taking payment.")
    method = data.get("method")
    if method not in PAYMENT_METHODS:
        raise ApiError("Choose a payment method: cash, card or UPI.")

    recalc(db, order_id)  # pick up any tax-rate change since the last edit
    total = db.execute("SELECT total FROM orders WHERE id = ?", (order_id,)).fetchone()[0]
    if method == "cash":
        tendered = as_int(data.get("amount_paid"), "Cash received", 0)
        if tendered < total:
            raise ApiError("Cash received is less than the bill total.")
    else:
        tendered = total
    change = tendered - total

    # Atomic bill number: the UPDATE takes SQLite's write lock for the whole transaction.
    db.execute("UPDATE settings SET value = CAST(value AS INTEGER) + 1 WHERE key = 'last_bill_no'")
    settings = get_settings(db)
    bill_no = f"{settings['bill_prefix']}-{int(settings['last_bill_no']):06d}"
    cur = db.execute(
        """UPDATE orders SET status = 'paid', bill_no = ?, payment_method = ?, amount_paid = ?,
                  change_due = ?, paid_at = datetime('now', 'localtime')
           WHERE id = ? AND status = 'open'""",
        (bill_no, method, tendered, change, order_id))
    if cur.rowcount != 1:
        db.rollback()
        raise ApiError("This order was already paid or cancelled on another device.", 409)
    db.commit()
    return jsonify(fetch_order(db, order_id))
