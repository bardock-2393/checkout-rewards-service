import asyncio
import uuid

from app.domain import Cart, CartStatus, Order, OrderLine
from app.errors import NotFoundError, OutOfStockError, ValidationError
from app.store import InMemoryStore


def _get_cart_and_lock(store: InMemoryStore, cart_id: str) -> tuple[Cart, asyncio.Lock]:
    cart = store.carts.get(cart_id)
    lock = store.cart_locks.get(cart_id)
    if cart is None or lock is None:
        raise NotFoundError(f"cart {cart_id} not found")
    return cart, lock


async def checkout(store: InMemoryStore, cart_id: str) -> Order:
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
            # Validate every line before mutating anything, so a single
            # out-of-stock item fails the whole checkout instead of partially
            # decrementing inventory.
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

            for line in lines:
                store.products[line.product_id].stock -= line.quantity

            subtotal = sum(line.subtotal_paise for line in lines)
            order = Order(
                id=str(uuid.uuid4()),
                cart_id=cart.id,
                lines=lines,
                subtotal_paise=subtotal,
                discount_paise=0,
                total_paise=subtotal,
                coupon_code=None,
            )
            store.orders[order.id] = order
            store.successful_order_count += 1

            cart.status = CartStatus.CHECKED_OUT
            cart.order_id = order.id

        return order


def get_order(store: InMemoryStore, order_id: str) -> Order:
    order = store.orders.get(order_id)
    if order is None:
        raise NotFoundError(f"order {order_id} not found")
    return order
