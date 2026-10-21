import asyncio

from tests.conftest import new_cart


async def checkout(client, product="p1"):
    cart_id = await new_cart(client, product, 1)
    return await client.post(f"/carts/{cart_id}/checkout")


async def test_generate_before_milestone_is_rejected(client):
    r = await client.post("/admin/coupons/generate")
    assert r.status_code == 409
    assert r.json()["error"] == "MILESTONE_NOT_REACHED"


async def test_generate_after_nth_order_succeeds_once(client):
    for _ in range(5):
        await checkout(client)

    r1 = await client.post("/admin/coupons/generate")
    assert r1.status_code == 200
    assert r1.json()["milestone"] == 1

    # already rewarded for this milestone - no backlog flooding
    r2 = await client.post("/admin/coupons/generate")
    assert r2.status_code == 409


async def test_invalid_coupon_code_is_rejected(client):
    cart_id = await new_cart(client, "p1", 1)
    r = await client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": "GARBAGE"})
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_COUPON"


async def test_coupon_applies_discount_and_can_only_be_used_once(client):
    for _ in range(5):
        await checkout(client)
    code = (await client.post("/admin/coupons/generate")).json()["code"]

    cart_id = await new_cart(client, "p2", 1)  # price 349900
    r = await client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": code})
    assert r.status_code == 200
    assert r.json()["discount_paise"] == 34990  # 10% floor-rounded
    assert r.json()["total_paise"] == 349900 - 34990

    cart_id_2 = await new_cart(client, "p3", 1)
    r2 = await client.post(f"/carts/{cart_id_2}/checkout", json={"coupon_code": code})
    assert r2.status_code == 409
    assert r2.json()["error"] == "COUPON_ALREADY_REDEEMED"


async def test_failed_checkout_does_not_consume_coupon(client):
    for _ in range(5):
        await checkout(client)
    code = (await client.post("/admin/coupons/generate")).json()["code"]

    # p5 only has 3 left; try to buy 10 with the coupon - checkout must fail
    # and the coupon must remain usable afterwards.
    cart_id = await new_cart(client, "p5", 10)
    failed = await client.post(f"/carts/{cart_id}/checkout", json={"coupon_code": code})
    assert failed.status_code == 409
    assert failed.json()["error"] == "OUT_OF_STOCK"

    cart_id_2 = await new_cart(client, "p4", 1)
    ok = await client.post(f"/carts/{cart_id_2}/checkout", json={"coupon_code": code})
    assert ok.status_code == 200
    assert ok.json()["coupon_code"] == code


async def test_concurrent_checkouts_only_one_redeems_the_coupon(client):
    for _ in range(5):
        await checkout(client)
    code = (await client.post("/admin/coupons/generate")).json()["code"]

    cart_ids = []
    for _ in range(6):
        cart_ids.append(await new_cart(client, "p1", 1))

    results = await asyncio.gather(
        *[client.post(f"/carts/{cid}/checkout", json={"coupon_code": code}) for cid in cart_ids]
    )
    redeemers = [r for r in results if r.status_code == 200 and r.json()["coupon_code"] == code]
    assert len(redeemers) == 1
