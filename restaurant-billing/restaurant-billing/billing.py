"""Pure bill-calculation logic (no database, no Flask) so it is easy to test.

All amounts are integer paise; rates are integer basis points (1% = 100).
"""


def pct(amount, basis_points):
    """amount * rate, rounded half-up to the nearest paisa."""
    return (amount * basis_points + 5000) // 10000


def compute_totals(subtotal, discount_type, discount_value, tax_bp, service_bp):
    if discount_type == "percent":
        discount = pct(subtotal, min(discount_value, 10000))
    elif discount_type == "flat":
        discount = min(discount_value, subtotal)  # never discount below zero
    else:
        discount = 0
    taxable = subtotal - discount
    tax = pct(taxable, tax_bp)
    service = pct(taxable, service_bp)
    raw_total = taxable + tax + service
    total = (raw_total + 50) // 100 * 100  # round to the nearest whole rupee
    return {
        "subtotal": subtotal,
        "discount_amount": discount,
        "tax_amount": tax,
        "service_amount": service,
        "round_off": total - raw_total,
        "total": total,
    }
