import httpx
import pytest

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app(coupon_every_n_orders=5, coupon_percent_off=10)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def new_cart(client, product_id: str = "p1", quantity: int = 1) -> str:
    cart_id = (await client.post("/carts")).json()["cart_id"]
    await client.post(f"/carts/{cart_id}/items", json={"product_id": product_id, "quantity": quantity})
    return cart_id
