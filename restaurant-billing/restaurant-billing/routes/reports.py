"""Sales reports (admin only)."""
from datetime import date, datetime

from flask import Blueprint, jsonify, request

from db import get_db
from routes.auth import login_required
from utils import ApiError

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _parse_day(text, default):
    if not text:
        return default
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ApiError("Dates must look like 2026-10-12.")


@bp.get("/summary")
@login_required("admin")
def summary():
    today = date.today()
    start = _parse_day(request.args.get("from"), today)
    end = _parse_day(request.args.get("to"), today)
    if start > end:
        raise ApiError("The start date must be on or before the end date.")
    span = (start.isoformat(), end.isoformat())
    db = get_db()
    paid = "o.status = 'paid' AND date(o.paid_at) BETWEEN ? AND ?"

    totals = dict(db.execute(
        f"""SELECT COUNT(*) AS orders, COALESCE(SUM(o.total), 0) AS net_sales,
                   COALESCE(SUM(o.subtotal), 0) AS gross_sales,
                   COALESCE(SUM(o.discount_amount), 0) AS discounts,
                   COALESCE(SUM(o.tax_amount), 0) AS tax,
                   COALESCE(SUM(o.service_amount), 0) AS service
            FROM orders o WHERE {paid}""", span).fetchone())
    totals["average_bill"] = totals["net_sales"] // totals["orders"] if totals["orders"] else 0

    by_method = [dict(r) for r in db.execute(
        f"""SELECT o.payment_method AS method, COUNT(*) AS orders, SUM(o.total) AS amount
            FROM orders o WHERE {paid} GROUP BY o.payment_method ORDER BY amount DESC""", span)]
    top_items = [dict(r) for r in db.execute(
        f"""SELECT i.name, SUM(i.qty) AS qty, SUM(i.qty * i.unit_price) AS amount
            FROM order_items i JOIN orders o ON o.id = i.order_id
            WHERE {paid} GROUP BY i.name ORDER BY qty DESC, amount DESC LIMIT 10""", span)]
    daily = [dict(r) for r in db.execute(
        f"""SELECT date(o.paid_at) AS day, COUNT(*) AS orders, SUM(o.total) AS amount
            FROM orders o WHERE {paid} GROUP BY day ORDER BY day DESC""", span)]
    cancelled = db.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'cancelled' AND date(created_at) BETWEEN ? AND ?",
        span).fetchone()[0]
    open_now = db.execute("SELECT COUNT(*) FROM orders WHERE status = 'open'").fetchone()[0]
    return jsonify(range={"from": span[0], "to": span[1]}, totals=totals, by_method=by_method,
                   top_items=top_items, daily=daily, cancelled=cancelled, open_orders=open_now)
