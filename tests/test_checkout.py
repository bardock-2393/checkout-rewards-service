import asyncio

from tests.conftest import new_cart


async def test_empty_cart_cannot_checkout(client):
    cart_id = (await client.post("/carts")).json()["cart_id"]
    r = await client.post(f"/carts/{cart_id}/checkout")
    assert r.status_code == 400
    assert r.json()["error"] == "VALIDATION_ERROR"


async def test_checkout_happy_path_decrements_stock(client):
    cart_id = await new_cart(client, "p1", 2)
    r = await client.post(f"/carts/{cart_id}/checkout")
    assert r.status_code == 200
    body = r.json()
    assert body["total_paise"] == 2 * 99900
    product = next(p for p in (await client.get("/products")).json() if p["id"] == "p1")
    assert product["stock"] == 48


async def test_retrying_checkout_is_idempotent(client):
    cart_id = await new_cart(client, "p1", 1)
    r1 = await client.post(f"/carts/{cart_id}/checkout")
    r2 = await client.post(f"/carts/{cart_id}/checkout")
    assert r1.json()["order_id"] == r2.json()["order_id"]
    product = next(p for p in (await client.get("/products")).json() if p["id"] == "p1")
    assert product["stock"] == 49  # only decremented once, not twice


async def test_checkout_fails_when_out_of_stock(client):
    cart_id = await new_cart(client, "p5", 10)  # p5 only has 3 in stock
    r = await client.post(f"/carts/{cart_id}/checkout")
    assert r.status_code == 409
    assert r.json()["error"] == "OUT_OF_STOCK"


async def test_concurrent_checkouts_never_oversell(client):
    # p5 has stock=3; 5 different carts race for 1 unit each.
    cart_ids = []
    for _ in range(5):
        cart_ids.append(await new_cart(client, "p5", 1))

    results = await asyncio.gather(*[client.post(f"/carts/{cid}/checkout") for cid in cart_ids])
    successes = [r for r in results if r.status_code == 200]
    failures = [r for r in results if r.status_code == 409]

    assert len(successes) == 3
    assert len(failures) == 2
    product = next(p for p in (await client.get("/products")).json() if p["id"] == "p5")
    assert product["stock"] == 0
