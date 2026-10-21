from tests.conftest import new_cart


async def test_add_unknown_product_is_not_found(client):
    cart_id = (await client.post("/carts")).json()["cart_id"]
    r = await client.post(f"/carts/{cart_id}/items", json={"product_id": "nope", "quantity": 1})
    assert r.status_code == 404
    assert r.json()["error"] == "NOT_FOUND"


async def test_add_non_positive_quantity_is_rejected(client):
    cart_id = (await client.post("/carts")).json()["cart_id"]
    r = await client.post(f"/carts/{cart_id}/items", json={"product_id": "p1", "quantity": 0})
    assert r.status_code == 422


async def test_view_cart_shows_live_totals(client):
    cart_id = await new_cart(client, "p1", 2)
    body = (await client.get(f"/carts/{cart_id}")).json()
    assert body["subtotal_paise"] == 2 * 99900
    assert body["items"][0]["available_stock"] == 50


async def test_update_and_remove_item(client):
    cart_id = await new_cart(client, "p1", 2)
    r = await client.patch(f"/carts/{cart_id}/items/p1", json={"quantity": 5})
    assert r.json()["items"][0]["quantity"] == 5
    r = await client.delete(f"/carts/{cart_id}/items/p1")
    assert r.json()["items"] == []


async def test_mutating_checked_out_cart_is_rejected(client):
    cart_id = await new_cart(client, "p1", 1)
    await client.post(f"/carts/{cart_id}/checkout")
    r = await client.post(f"/carts/{cart_id}/items", json={"product_id": "p2", "quantity": 1})
    assert r.status_code == 409
    assert r.json()["error"] == "CART_ALREADY_CHECKED_OUT"
