"""Order pricing engine with intentional calculation ordering bugs."""

from __future__ import annotations

from typing import List, Optional


LOYALTY_RATES = {
    "VIP": 0.15,
    "GOLD": 0.10,
    "SILVER": 0.05,
}


def calculate_order_total(
    item_prices: List[float],
    loyalty_tier: Optional[str] = None,
    coupon_code: Optional[str] = None,
    tax_rate: float = 0.08,
) -> dict:
    """Calculate subtotal, discount, tax, and final total for an order."""
    raw_subtotal = sum(item_prices)
    current = raw_subtotal

    # BUG: Applies coupon before loyalty tier and allows negative subtotal
    if coupon_code == "SAVE10":
        current -= 10.0
    elif coupon_code == "HALF":
        current *= 0.5

    if loyalty_tier in LOYALTY_RATES:
        current -= raw_subtotal * LOYALTY_RATES[loyalty_tier]

    tax = round(raw_subtotal * tax_rate, 2)  # BUG: calculates tax on raw_subtotal instead of post-discount
    total = round(current + tax, 2)
    return {
        "raw_subtotal": round(raw_subtotal, 2),
        "discounted_subtotal": round(current, 2),
        "tax": tax,
        "total": total,
    }
