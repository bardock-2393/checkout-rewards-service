import asyncio
import uuid

from app.domain import Cart, CartStatus, Order, OrderLine
from app.errors import NotFoundError, OutOfStockError, ValidationError
from app.services import coupon_service
from app.store import InMemoryStore


def _get_cart_and_lock(store: InMemoryStore, cart_id: str) -> tuple[Cart, asyncio.Lock]:
    cart = store.carts.get(cart_id)
    lock = store.cart_locks.get(cart_id)
    if cart is None or lock is None:
        raise NotFoundError(f"cart {cart_id} not found")
    return cart, lock


async def checkout(store: InMemoryStore, cart_id: str, coupon_code: str | None = None) -> Order:
    cart, cart_lock = _get_cart_and_lock(store, cart_id)

    async with cart_lock:
        # Idempotent retry: a cart can only ever produce one order. If this
        # cart already checked out (e.g. a client retried after a timeout),
        # hand back the same order instead of creating a second one.
        if cart.status is CartStatus.CHECKED_OUT:
            return store.orders[cart.order_id]

        if not cart.items:
            raise ValidationError("cart is empty")

        async with store.global_lock:
            # Validate everything - stock AND coupon - before mutating
            # anything. A coupon must never be consumed by a checkout that
            # ultimately fails on inventory, and vice versa.
            lines: list[OrderLine] = []
            for product_id, quantity in cart.items.items():
                product = store.products.get(product_id)
                if product is None:
                    raise NotFoundError(f"product {product_id} no longer exists")
                if product.stock < quantity:
                    raise OutOfStockError(
                        f"only {product.stock} of {product.name} left, requested {quantity}"
                    )
                lines.append(
                    OrderLine(
                        product_id=product.id,
                        name=product.name,
                        unit_price_paise=product.price_paise,
                        quantity=quantity,
                    )
                )

            coupon = coupon_service.validate_coupon(store, coupon_code) if coupon_code else None

            for line in lines:
                store.products[line.product_id].stock -= line.quantity

            subtotal = sum(line.subtotal_paise for line in lines)
            discount = coupon_service.discount_for(subtotal, coupon.percent_off) if coupon else 0

            order = Order(
                id=str(uuid.uuid4()),
                cart_id=cart.id,
                lines=lines,
                subtotal_paise=subtotal,
                discount_paise=discount,
                total_paise=subtotal - discount,
                coupon_code=coupon.code if coupon else None,
            )
            store.orders[order.id] = order
            store.successful_order_count += 1

            if coupon:
                coupon_service.redeem(coupon)

            cart.status = CartStatus.CHECKED_OUT
            cart.order_id = order.id

        return order


def get_order(store: InMemoryStore, order_id: str) -> Order:
    order = store.orders.get(order_id)
    if order is None:
        raise NotFoundError(f"order {order_id} not found")
    return order
