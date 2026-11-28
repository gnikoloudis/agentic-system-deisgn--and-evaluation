# Epic: Dynamic Discount Calculation Engine

## User Story: US-042 - Tiered Volume & Loyalty Discount Pricing

**As an** E-Commerce Checkout Service,  
**I want** to calculate order discounts based on order subtotal, volume tier, and customer loyalty status,  
**So that** high-value customers receive accurate promotional pricing automatically.

### Acceptance Criteria:
1. **Base Tier (Subtotal < $100)**:
   - 0% volume discount.
2. **Tier 1 ($100 <= Subtotal < $500)**:
   - 5% volume discount applied to subtotal.
3. **Tier 2 (Subtotal >= $500)**:
   - 10% volume discount applied to subtotal.
4. **Loyalty Multiplier**:
   - If customer has `loyalty_status == "gold"`, grant an extra 5% discount (additive).
   - If customer has `loyalty_status == "platinum"`, grant an extra 10% discount (additive).
   - Max allowed cumulative discount cap is 20%.
5. **Validation / Error Handling**:
   - Subtotal must be non-negative. Raise `ValueError` if `subtotal < 0`.
   - Result must return `Decimal` rounded to 2 decimal places.
