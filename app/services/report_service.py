from app.domain import CouponStatus
from app.store import InMemoryStore


def build_report(store: InMemoryStore) -> dict:
    """
    Read-only aggregation over orders/coupons. No lock needed: this function
    never awaits, so it can't be interleaved with a mutating handler - it
    either runs entirely before or entirely after any given checkout.
    """
    purchased_by_product: dict[str, int] = {}
    gross_revenue = 0
    total_discounts = 0

    for order in store.orders.values():
        gross_revenue += order.subtotal_paise
        total_discounts += order.discount_paise
        for line in order.lines:
            purchased_by_product[line.product_id] = (
                purchased_by_product.get(line.product_id, 0) + line.quantity
            )

    coupons = list(store.coupons.values())
    coupons_redeemed = sum(1 for c in coupons if c.status is CouponStatus.REDEEMED)

    return {
        "purchased_quantity_by_product": purchased_by_product,
        "gross_revenue_paise": gross_revenue,
        "total_discounts_paise": total_discounts,
        "net_revenue_paise": gross_revenue - total_discounts,
        "coupons_generated": len(coupons),
        "coupons_available": len(coupons) - coupons_redeemed,
        "coupons_redeemed": coupons_redeemed,
        "total_orders": len(store.orders),
    }
