"""Run with:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from billing import compute_totals, pct  # noqa: E402


class BillingMathTests(unittest.TestCase):
    def test_percent_rounds_half_up(self):
        self.assertEqual(pct(1050, 500), 53)  # 52.5 -> 53
        self.assertEqual(pct(0, 500), 0)

    def test_percent_discount_tax_and_rounding(self):
        t = compute_totals(20000, "percent", 1000, 500, 0)  # 10% off, 5% tax
        self.assertEqual(t["discount_amount"], 2000)
        self.assertEqual(t["tax_amount"], 900)
        self.assertEqual(t["total"], 18900)

    def test_flat_discount_never_exceeds_subtotal(self):
        t = compute_totals(5000, "flat", 999999, 500, 0)
        self.assertEqual(t["discount_amount"], 5000)
        self.assertEqual(t["total"], 0)

    def test_total_rounds_to_whole_rupee(self):
        t = compute_totals(24900, "none", 0, 500, 0)  # 249 + 12.45 = 261.45
        self.assertEqual(t["total"], 26100)
        self.assertEqual(t["round_off"], -45)

    def test_service_charge_added(self):
        t = compute_totals(10000, "none", 0, 500, 1000)
        self.assertEqual((t["tax_amount"], t["service_amount"], t["total"]), (500, 1000, 11500))


class ApiTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.path)
        self.app = create_app({"DATABASE": self.path, "TESTING": True, "SECRET_KEY": "test"})
        self.c = self.app.test_client()
        self.login("cashier", "cashier123")

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.path + suffix):
                os.unlink(self.path + suffix)

    def login(self, user, password):
        r = self.c.post("/api/auth/login", json={"username": user, "password": password})
        self.assertEqual(r.status_code, 200, r.get_json())

    def item(self, name):
        items = self.c.get("/api/menu").get_json()["items"]
        return next(i for i in items if i["name"] == name)

    def new_order(self, table_id=1):
        return self.c.post("/api/orders", json={"order_type": "dine_in", "table_id": table_id}).get_json()

    def test_requires_login(self):
        self.c.post("/api/auth/logout")
        self.assertEqual(self.c.get("/api/menu").status_code, 401)
        r = self.c.post("/api/auth/login", json={"username": "admin", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_full_flow_order_to_paid_bill(self):
        order = self.new_order()
        oid = order["id"]
        naan, dal = self.item("Butter Naan"), self.item("Dal Makhani")
        self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": naan["id"], "qty": 2})
        o = self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": dal["id"]}).get_json()
        self.assertEqual(o["subtotal"], 2 * 5500 + 24000)
        # adding the same item again merges into one line
        o = self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": naan["id"]}).get_json()
        self.assertEqual(len(o["items"]), 2)
        self.assertEqual(o["items"][0]["qty"], 3)
        o = self.c.patch(f"/api/orders/{oid}", json={"discount_type": "percent", "discount_value": 1000}).get_json()
        self.assertEqual(o["discount_amount"], pct(o["subtotal"], 1000))
        self.assertEqual(o["total"] % 100, 0)

        short = self.c.post(f"/api/orders/{oid}/pay", json={"method": "cash", "amount_paid": 100})
        self.assertEqual(short.status_code, 400)
        paid = self.c.post(f"/api/orders/{oid}/pay", json={"method": "cash", "amount_paid": o["total"] + 5000})
        self.assertEqual(paid.status_code, 200)
        p = paid.get_json()
        self.assertEqual((p["status"], p["bill_no"], p["change_due"]), ("paid", "INV-000001", 5000))
        # paid orders are locked
        again = self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": naan["id"]})
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.c.post(f"/api/orders/{oid}/pay", json={"method": "upi"}).status_code, 409)
        # table is free again and the next bill number increments
        o2 = self.new_order()
        self.assertNotEqual(o2["id"], oid)
        self.c.post(f"/api/orders/{o2['id']}/items", json={"menu_item_id": naan["id"]})
        p2 = self.c.post(f"/api/orders/{o2['id']}/pay", json={"method": "upi"}).get_json()
        self.assertEqual(p2["bill_no"], "INV-000002")

    def test_table_reuses_its_open_order(self):
        a, b = self.new_order(2), self.new_order(2)
        self.assertEqual(a["id"], b["id"])

    def test_cannot_pay_empty_order_or_use_bad_inputs(self):
        oid = self.new_order(3)["id"]
        self.assertEqual(self.c.post(f"/api/orders/{oid}/pay", json={"method": "cash", "amount_paid": 0}).status_code, 400)
        self.assertEqual(self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": 1, "qty": 0}).status_code, 400)
        self.assertEqual(self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": 1, "qty": 100}).status_code, 400)
        self.assertEqual(self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": 99999}).status_code, 404)
        self.assertEqual(self.c.post("/api/orders", json={"order_type": "dine_in", "table_id": 999}).status_code, 404)
        self.assertEqual(self.c.post("/api/orders", data="not json").status_code, 400)

    def test_sold_out_item_cannot_be_added(self):
        self.c.post("/api/auth/logout")
        self.login("admin", "admin123")
        naan = self.item("Butter Naan")
        self.assertEqual(self.c.put(f"/api/menu-items/{naan['id']}", json={"is_available": False}).status_code, 200)
        oid = self.new_order(4)["id"]
        r = self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": naan["id"]})
        self.assertEqual(r.status_code, 409)

    def test_menu_price_change_does_not_alter_existing_lines(self):
        oid = self.new_order(5)["id"]
        naan = self.item("Butter Naan")
        self.c.post(f"/api/orders/{oid}/items", json={"menu_item_id": naan["id"]})
        self.c.post("/api/auth/logout")
        self.login("admin", "admin123")
        self.c.put(f"/api/menu-items/{naan['id']}", json={"price": 99900})
        o = self.c.get(f"/api/orders/{oid}").get_json()
        self.assertEqual(o["items"][0]["unit_price"], 5500)

    def test_cancel_order_frees_table(self):
        oid = self.new_order(6)["id"]
        r = self.c.post(f"/api/orders/{oid}/cancel", json={"reason": "Guests left"})
        self.assertEqual(r.get_json()["status"], "cancelled")
        self.assertNotEqual(self.new_order(6)["id"], oid)

    def test_takeaway_order(self):
        o = self.c.post("/api/orders", json={"order_type": "takeaway", "customer_name": "Ravi"}).get_json()
        self.assertIsNone(o["table_id"])
        self.assertEqual(o["customer_name"], "Ravi")

    def test_admin_only_endpoints(self):
        self.assertEqual(self.c.get("/api/reports/summary").status_code, 403)
        self.assertEqual(self.c.post("/api/categories", json={"name": "Specials"}).status_code, 403)
        self.assertEqual(self.c.put("/api/settings", json={}).status_code, 403)

    def test_admin_manages_menu_and_settings(self):
        self.c.post("/api/auth/logout")
        self.login("admin", "admin123")
        self.assertEqual(self.c.post("/api/categories", json={"name": "Specials"}).status_code, 201)
        self.assertEqual(self.c.post("/api/categories", json={"name": "specials"}).status_code, 409)
        cat = next(c for c in self.c.get("/api/menu").get_json()["categories"] if c["name"] == "Specials")
        r = self.c.post("/api/menu-items", json={"name": "Thali", "category_id": cat["id"], "price": 19900})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.c.post("/api/menu-items", json={"name": "thali", "category_id": cat["id"], "price": 100}).status_code, 409)
        self.assertEqual(self.c.delete(f"/api/categories/{cat['id']}").status_code, 409)
        self.assertEqual(self.c.post("/api/menu-items", json={"name": "Bad", "category_id": cat["id"], "price": -5}).status_code, 400)
        s = self.c.put("/api/settings", json={
            "restaurant_name": "Test Cafe", "address": "", "gstin": "", "currency": "₹",
            "tax_percent": "12.5", "service_percent": "0", "bill_prefix": "tc"})
        self.assertEqual(s.status_code, 200)
        self.assertEqual(s.get_json()["bill_prefix"], "TC")
        bad = self.c.put("/api/settings", json={
            "restaurant_name": "X", "currency": "₹", "tax_percent": "150", "service_percent": "0", "bill_prefix": "A"})
        self.assertEqual(bad.status_code, 400)

    def test_reports_reflect_paid_orders_only(self):
        naan = self.item("Butter Naan")
        paid_id = self.new_order(1)["id"]
        self.c.post(f"/api/orders/{paid_id}/items", json={"menu_item_id": naan["id"], "qty": 2})
        total = self.c.get(f"/api/orders/{paid_id}").get_json()["total"]
        self.c.post(f"/api/orders/{paid_id}/pay", json={"method": "card"})
        open_id = self.new_order(2)["id"]
        self.c.post(f"/api/orders/{open_id}/items", json={"menu_item_id": naan["id"]})
        self.c.post("/api/auth/logout")
        self.login("admin", "admin123")
        rep = self.c.get("/api/reports/summary").get_json()
        self.assertEqual(rep["totals"]["orders"], 1)
        self.assertEqual(rep["totals"]["net_sales"], total)
        self.assertEqual(rep["by_method"][0]["method"], "card")
        self.assertEqual(rep["top_items"][0]["qty"], 2)
        self.assertEqual(rep["open_orders"], 1)
        self.assertEqual(self.c.get("/api/reports/summary?from=2026-10-12&to=2026-01-01").status_code, 400)
        self.assertEqual(self.c.get("/api/reports/summary?from=garbage").status_code, 400)

    def test_order_search_and_filters(self):
        oid = self.new_order(7)["id"]
        self.c.patch(f"/api/orders/{oid}", json={"customer_name": "Sharma"})
        hits = self.c.get("/api/orders?q=sharma").get_json()
        self.assertEqual([h["id"] for h in hits], [oid])
        self.assertEqual(self.c.get("/api/orders?status=paid").get_json(), [])
        self.assertEqual(self.c.get("/api/orders?q=%25").get_json(), [])  # '%' is not a wildcard


if __name__ == "__main__":
    unittest.main()
