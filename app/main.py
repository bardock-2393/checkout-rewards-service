from fastapi import FastAPI, Request

from app.errors import register_error_handlers
from app.routers import admin, carts, orders
from app.store import InMemoryStore


def create_app(coupon_every_n_orders: int = 5, coupon_percent_off: int = 10) -> FastAPI:
    app = FastAPI(title="Checkout & Rewards Service")
    app.state.store = InMemoryStore(
        coupon_every_n_orders=coupon_every_n_orders,
        coupon_percent_off=coupon_percent_off,
    )

    register_error_handlers(app)
    app.include_router(carts.router)
    app.include_router(orders.router)
    app.include_router(admin.router)

    @app.get("/products")
    def list_products(request: Request):
        store: InMemoryStore = request.app.state.store
        return [
            {
                "id": p.id,
                "name": p.name,
                "price_paise": p.price_paise,
                "stock": p.stock,
            }
            for p in store.products.values()
        ]

    return app


app = create_app()
