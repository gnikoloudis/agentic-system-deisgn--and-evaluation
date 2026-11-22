"""Unit tests for order pricing engine."""

from pricing import calculate_order_total


def test_loyalty_then_save10_coupon_and_tax():
    # Raw subtotal = 100.00
    # VIP loyalty (15%) -> 85.00
    # SAVE10 coupon -> 75.00
    # Tax (10%) on 75.00 -> 7.50
    # Final total -> 82.50
    res = calculate_order_total([60.0, 40.0], loyalty_tier="VIP", coupon_code="SAVE10", tax_rate=0.10)
    assert res["raw_subtotal"] == 100.00
    assert res["discounted_subtotal"] == 75.00
    assert res["tax"] == 7.50
    assert res["total"] == 82.50


def test_loyalty_then_half_coupon():
    # Raw subtotal = 200.00
    # GOLD loyalty (10%) -> 180.00
    # HALF coupon (50% off after loyalty) -> 90.00
    # Tax (8%) on 90.00 -> 7.20
    # Final total -> 97.20
    res = calculate_order_total([200.0], loyalty_tier="GOLD", coupon_code="HALF", tax_rate=0.08)
    assert res["discounted_subtotal"] == 90.00
    assert res["tax"] == 7.20
    assert res["total"] == 97.20


def test_coupon_floor_at_zero():
    # Raw subtotal = 5.00, SAVE10 should floor at 0.00 with 0.00 tax
    res = calculate_order_total([5.0], loyalty_tier="SILVER", coupon_code="SAVE10", tax_rate=0.10)
    assert res["discounted_subtotal"] == 0.00
    assert res["tax"] == 0.00
    assert res["total"] == 0.00
