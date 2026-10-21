from fastapi import APIRouter, Request

from app.domain import Order
from app.services import checkout_service

router = APIRouter(tags=["orders"])


def _serialize(order: Order) -> dict:
    return {
        "order_id": order.id,
        "cart_id": order.cart_id,
        "lines": [
            {
                "product_id": line.product_id,
                "name": line.name,
                "unit_price_paise": line.unit_price_paise,
                "quantity": line.quantity,
                "subtotal_paise": line.subtotal_paise,
            }
            for line in order.lines
        ],
        "subtotal_paise": order.subtotal_paise,
        "discount_paise": order.discount_paise,
        "total_paise": order.total_paise,
        "coupon_code": order.coupon_code,
    }


@router.post("/carts/{cart_id}/checkout")
async def checkout(cart_id: str, request: Request):
    store = request.app.state.store
    order = await checkout_service.checkout(store, cart_id)
    return _serialize(order)


@router.get("/orders/{order_id}")
def get_order(order_id: str, request: Request):
    store = request.app.state.store
    order = checkout_service.get_order(store, order_id)
    return _serialize(order)
