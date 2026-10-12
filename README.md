# Restaurant Billing & Management System

A small, fast billing system for a restaurant floor: **take an order at a table → add items → apply a discount → collect payment → print the bill**, plus menu management and sales reports.

Built for the one-day technical assessment. It is a complete, working app with no build step and no external services.

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | HTML, CSS, vanilla JavaScript (ES modules) | No build tooling; opens straight from the Flask server |
| Backend | Python 3.9+ with Flask | Small, readable, easy to run anywhere |
| Database | SQLite (plain SQL, no ORM) | Zero setup, one file, transactional, ideal for a single restaurant |
| Tests | `unittest` (backend) | No extra dependencies |

The only Python dependency is Flask (`requirements.txt`).

## Run it

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. install the one dependency
pip install -r requirements.txt

# 3. start the app
python app.py
```

Open **http://127.0.0.1:5000**.

No database setup is needed. On first start the app creates `instance/restaurant.db` from `schema.sql` and loads demo data (menu, tables, two users).

To use it from a tablet or phone on the same Wi-Fi: `HOST=0.0.0.0 python app.py` (Windows PowerShell: `$env:HOST="0.0.0.0"; python app.py`), then open `http://<this-computer's-IP>:5000`.

To reset everything to the demo data, stop the app and delete `instance/restaurant.db`.

Optional environment variables: `HOST` (default `127.0.0.1`), `PORT` (default `5000`), `SECRET_KEY` (otherwise one is generated once and kept in `instance/secret_key`).

### Demo credentials

| Role | Username | Password | Can do |
| --- | --- | --- | --- |
| Admin | `admin` | `admin123` | Everything, including menu, reports and setup |
| Cashier | `cashier` | `cashier123` | Floor, orders, billing and order history |

### Run the tests

```bash
python -m unittest discover -s tests -v
```

17 tests cover the billing maths and the API: the full order-to-paid flow, validation, sold-out items, price snapshots, role permissions, reports and search.

## Features

**Taking orders**
- Floor view with every table: free, or amber with the running total, item count and open time. It refreshes every 15 seconds so several devices stay in sync.
- One open order per table (enforced by the database). Tapping a busy table resumes its order.
- Takeaway orders with an optional customer name.
- Tap-to-add menu with category filters and search. Press **Enter** in the search box to add the first match, which is fast on a keyboard.
- Quantity +/−, remove line, and a per-item kitchen note ("less spicy").
- Veg / non-veg markers, and sold-out items that can't be added.

**Billing**
- Discount as a percentage or a flat amount (can never push the bill below zero).
- Configurable tax (GST) and optional service charge, with a line for each.
- Total rounds to the nearest rupee and shows the round-off.
- Payment by cash, card or UPI. For cash: quick-amount buttons, live "change to return" or "short by", and the Confirm button stays disabled until enough is received.
- Sequential bill numbers (`INV-000001`) assigned atomically at payment.
- Printable receipt (a pre-bill can be printed before payment). Paid orders are locked.
- Cancel an open order with an optional reason.

**Management (admin)**
- Menu: add, edit and delete items; categories (add, rename, delete); mark an item sold out in one tap.
- Setup: restaurant name, address, GSTIN, currency symbol, bill prefix, tax % and service %. Add, edit and remove tables.
- Reports for any date range: net sales, paid bills, average bill, tax collected, discounts, payment-method split, top 10 items and sales by day.

**Order history**
- Search by bill number, order number, table or customer, and filter by status and date. Open any past order to see its receipt.

**Security and reliability**
- Sign-in with hashed passwords (Werkzeug), cookie sessions, and role checks on the server for every admin endpoint.
- Every input is validated on the server; errors come back as plain messages shown in the UI.
- All user text is HTML-escaped before display; SQL is fully parameterised.

## Architecture

```
restaurant-billing/
├── app.py            Flask app factory, error handlers, entry point
├── db.py             SQLite connection per request, schema setup, settings helper
├── schema.sql        All tables, constraints and indexes
├── seed.py           Demo data (users, menu, tables, settings)
├── billing.py        Pure bill maths: discount, tax, service, rounding (no I/O)
├── utils.py          ApiError and input validators
├── routes/
│   ├── auth.py       Login / logout / role decorator
│   ├── orders.py     Tables, orders, items, discount, payment, cancel
│   ├── admin.py      Menu, categories, tables, settings
│   └── reports.py    Sales summary
├── static/
│   ├── index.html    Single page shell
│   ├── css/style.css
│   └── js/           app.js (router) · pos.js (floor, order, payment) · history.js
│                     admin.js (menu, setup) · reports.js · receipt.js · api.js · state.js · util.js
└── tests/test_app.py
```

**Separation of concerns.** Routes only parse and validate requests and call SQL. The money maths lives in `billing.py` so it can be tested without a database. The frontend has one module per screen, one API client, and one set of formatting helpers.

**Request flow.** The browser is a single-page app using hash routes (`#/floor`, `#/order/12`, `#/reports`). It talks to a JSON API under `/api/...`. The server is the source of truth: each change returns the full updated order and the screen redraws from it.

### Data model

```
users ─┐
       └< orders >── order_items >── menu_items >── categories
              │
              └── dining_tables          settings (key/value, incl. bill counter)
```

Key decisions:

- **Money is stored as integer paise** and rates as integer basis points, so there are no floating-point errors. Rounding is half-up and happens in one place (`billing.py`).
- **Order lines copy the item name and price** at the time of ordering, so editing the menu never changes an open or past bill.
- **Menu items are soft-deleted**, so history and reports keep working.
- **A partial unique index** (`one open order per table`) means two cashiers can't open the same table twice, even at the same instant.
- **Bill numbers** come from a counter updated inside the same transaction that marks the order paid, so numbers are never duplicated or skipped by a failed payment.
- **Totals are stored on the order** and recomputed on every change. When an order is paid, its tax and service rates are frozen on the row.

### API overview

All routes are under `/api` and need a session unless noted. "Admin" means admin role only.

| Method & path | Purpose |
| --- | --- |
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Session (login needs no session) |
| `GET /menu` | Categories and active items |
| `POST/PUT/DELETE /menu-items[/id]`, `POST/PUT/DELETE /categories[/id]` | Menu management (admin) |
| `GET /tables` | Tables with their open order, if any |
| `POST/PUT/DELETE /tables[/id]` | Table management (admin) |
| `GET /orders?status=&type=&date=&q=` | List and search orders |
| `POST /orders` | Create (or resume) an order |
| `GET /orders/<id>` | One order with its items |
| `PATCH /orders/<id>` | Customer name, discount |
| `POST /orders/<id>/items`, `PATCH`/`DELETE /orders/<id>/items/<line>` | Add, change, remove lines |
| `POST /orders/<id>/pay` | Take payment `{method, amount_paid}` |
| `POST /orders/<id>/cancel` | Cancel an open order |
| `GET`/`PUT /settings` | Read (all) / update (admin) |
| `GET /reports/summary?from=&to=` | Sales report (admin) |

All money is in paise. For discounts, `discount_value` is basis points when the type is `percent` (1000 = 10%) and paise when the type is `flat`.

## Known issues and limitations

- Users can't be managed from the UI. To change a password, generate a hash and update the row:
  `python -c "from werkzeug.security import generate_password_hash as g; print(g('NewPass'))"`, then `UPDATE users SET password_hash='<hash>' WHERE username='admin';` in the SQLite file. **Change the demo passwords before real use.**
- A tax or service rate change reaches an open order the next time it is edited or billed, not instantly. Paid bills are never changed.
- One tax rate for the whole menu (no per-item GST slabs, no CGST/SGST split).
- Dates and times use the server's local clock.
- The floor refreshes by polling every 15 seconds rather than live push.
- A paid bill can't be refunded or voided in the app.
- Built-in Flask server is for demos and a single venue. For a real deployment run it behind a production WSGI server (for example `waitress` or `gunicorn`) over HTTPS.
- Browser tests were run manually against Chromium. The automated tests cover the backend only.

## What I would build next

1. User management screen, forced password change, and an activity log of who did what.
2. Kitchen display / kitchen order tickets, with item status (new, preparing, served).
3. Split bills and merging or moving tables.
4. Refunds and bill voids with a reason and an admin approval.
5. Per-item tax slabs and a proper GST invoice (CGST/SGST).
6. Inventory and recipe costing with low-stock alerts.
7. Reservations and customer records.
8. Export reports to CSV/PDF, and an end-of-day cash-drawer reconciliation.
9. Live updates over WebSockets, and an offline-capable PWA.
10. Browser end-to-end tests in CI.
