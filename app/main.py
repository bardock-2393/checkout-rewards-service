from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routers import admin, carts, orders
from app.store import InMemoryStore

app = FastAPI(title="Checkout & Rewards Service")
app.state.store = InMemoryStore(coupon_every_n_orders=5, coupon_percent_off=10)

register_error_handlers(app)
app.include_router(carts.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/products")
def list_products():
    store: InMemoryStore = app.state.store
    return [
        {
            "id": p.id,
            "name": p.name,
            "price_paise": p.price_paise,
            "stock": p.stock,
        }
        for p in store.products.values()
    ]
