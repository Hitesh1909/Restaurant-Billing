"""Demo data loaded the first time the app starts."""
from werkzeug.security import generate_password_hash

CATEGORIES = ["Starters", "Main Course", "Breads", "Rice & Biryani", "Desserts", "Beverages"]

# (category, name, price in rupees, veg?)
ITEMS = [
    ("Starters", "Paneer Tikka", 260, 1), ("Starters", "Veg Spring Roll", 180, 1),
    ("Starters", "Chicken 65", 280, 0), ("Starters", "Tomato Soup", 120, 1),
    ("Main Course", "Dal Makhani", 240, 1), ("Main Course", "Paneer Butter Masala", 290, 1),
    ("Main Course", "Kadai Chicken", 340, 0), ("Main Course", "Mutton Rogan Josh", 420, 0),
    ("Main Course", "Mix Veg Curry", 210, 1),
    ("Breads", "Butter Naan", 55, 1), ("Breads", "Tandoori Roti", 30, 1),
    ("Breads", "Garlic Naan", 70, 1), ("Breads", "Lachha Paratha", 60, 1),
    ("Rice & Biryani", "Steamed Rice", 120, 1), ("Rice & Biryani", "Veg Biryani", 250, 1),
    ("Rice & Biryani", "Chicken Biryani", 320, 0), ("Rice & Biryani", "Jeera Rice", 140, 1),
    ("Desserts", "Gulab Jamun (2 pcs)", 90, 1), ("Desserts", "Rasmalai (2 pcs)", 120, 1),
    ("Desserts", "Vanilla Ice Cream", 80, 1),
    ("Beverages", "Masala Chai", 30, 1), ("Beverages", "Fresh Lime Soda", 70, 1),
    ("Beverages", "Sweet Lassi", 90, 1), ("Beverages", "Cold Coffee", 110, 1),
    ("Beverages", "Mineral Water", 25, 1),
]

SETTINGS = {
    "restaurant_name": "Spice Route Kitchen",
    "address": "12 Station Road, Gaya, Bihar",
    "gstin": "",
    "currency": "₹",
    "tax_percent": "5",
    "service_percent": "0",
    "bill_prefix": "INV",
    "last_bill_no": "0",
}


def seed_demo_data(db):
    db.executemany(
        "INSERT INTO users (username, name, password_hash, role) VALUES (?, ?, ?, ?)",
        [
            ("admin", "Admin", generate_password_hash("admin123"), "admin"),
            ("cashier", "Cashier", generate_password_hash("cashier123"), "cashier"),
        ],
    )
    db.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", SETTINGS.items())
    for order, name in enumerate(CATEGORIES):
        db.execute("INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, order))
    category_ids = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM categories")}
    db.executemany(
        "INSERT INTO menu_items (category_id, name, price, is_veg) VALUES (?, ?, ?, ?)",
        [(category_ids[c], n, p * 100, v) for c, n, p, v in ITEMS],
    )
    seats = [2, 2, 4, 4, 4, 4, 6, 8]
    db.executemany(
        "INSERT INTO dining_tables (name, seats) VALUES (?, ?)",
        [(f"T{i + 1}", s) for i, s in enumerate(seats)],
    )
