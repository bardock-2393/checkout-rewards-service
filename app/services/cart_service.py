import asyncio
import uuid

from app.domain import Cart, CartStatus
from app.errors import CartAlreadyCheckedOutError, NotFoundError
from app.store import InMemoryStore


def create_cart(store: InMemoryStore) -> Cart:
    cart = Cart(id=str(uuid.uuid4()))
    store.carts[cart.id] = cart
    store.cart_locks[cart.id] = asyncio.Lock()
    return cart


def get_cart(store: InMemoryStore, cart_id: str) -> Cart:
    cart = store.carts.get(cart_id)
    if cart is None:
        raise NotFoundError(f"cart {cart_id} not found")
    return cart


def _require_open(cart: Cart) -> None:
    if cart.status is not CartStatus.OPEN:
        raise CartAlreadyCheckedOutError(f"cart {cart.id} is already checked out")


def add_item(store: InMemoryStore, cart_id: str, product_id: str, quantity: int) -> Cart:
    cart = get_cart(store, cart_id)
    _require_open(cart)
    if product_id not in store.products:
        raise NotFoundError(f"product {product_id} not found")
    cart.items[product_id] = cart.items.get(product_id, 0) + quantity
    return cart


def update_item(store: InMemoryStore, cart_id: str, product_id: str, quantity: int) -> Cart:
    cart = get_cart(store, cart_id)
    _require_open(cart)
    if product_id not in cart.items:
        raise NotFoundError(f"product {product_id} is not in cart {cart_id}")
    cart.items[product_id] = quantity
    return cart


def remove_item(store: InMemoryStore, cart_id: str, product_id: str) -> Cart:
    cart = get_cart(store, cart_id)
    _require_open(cart)
    if product_id not in cart.items:
        raise NotFoundError(f"product {product_id} is not in cart {cart_id}")
    del cart.items[product_id]
    return cart


def view_cart(store: InMemoryStore, cart_id: str) -> dict:
    cart = get_cart(store, cart_id)
    lines = []
    subtotal = 0
    for product_id, quantity in cart.items.items():
        product = store.products.get(product_id)
        if product is None:
            continue
        line_subtotal = product.price_paise * quantity
        subtotal += line_subtotal
        lines.append(
            {
                "product_id": product.id,
                "name": product.name,
                "unit_price_paise": product.price_paise,
                "quantity": quantity,
                "available_stock": product.stock,
                "subtotal_paise": line_subtotal,
            }
        )
    return {
        "cart_id": cart.id,
        "status": cart.status.value,
        "order_id": cart.order_id,
        "items": lines,
        "subtotal_paise": subtotal,
    }
