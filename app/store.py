import asyncio

from app.domain import Cart, Coupon, Order, Product


class InMemoryStore:
    """
    All shared mutable state for the service.

    Two lock granularities, always acquired in this order (cart lock first,
    then global lock) to avoid deadlocks:

    - `cart_locks[cart_id]`: serializes repeated/concurrent checkout attempts
      against the SAME cart (so a retried or double-submitted request can't
      race itself).
    - `global_lock`: serializes access to state shared ACROSS carts -
      product stock, the order counter, and coupons. Any two carts
      checking out at once still contend for the same inventory/coupons,
      so this has to be a single lock, not one per product.
    """

    def __init__(self, coupon_every_n_orders: int = 5, coupon_percent_off: int = 10):
        self.products: dict[str, Product] = {}
        self.carts: dict[str, Cart] = {}
        self.cart_locks: dict[str, asyncio.Lock] = {}
        self.orders: dict[str, Order] = {}
        self.coupons: dict[str, Coupon] = {}

        self.global_lock = asyncio.Lock()
        self.successful_order_count = 0
        self.last_rewarded_milestone = 0

        self.coupon_every_n_orders = coupon_every_n_orders
        self.coupon_percent_off = coupon_percent_off

        self._seed_products()

    def _seed_products(self) -> None:
        seed = [
            Product(id="p1", name="Wireless Mouse", price_paise=99900, stock=50),
            Product(id="p2", name="Mechanical Keyboard", price_paise=349900, stock=30),
            Product(id="p3", name="USB-C Hub", price_paise=179900, stock=40),
            Product(id="p4", name="Laptop Stand", price_paise=129900, stock=25),
            Product(id="p5", name="4K Webcam", price_paise=599900, stock=3),  # limited inventory
        ]
        for product in seed:
            self.products[product.id] = product
