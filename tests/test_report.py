from tests.conftest import new_cart


async def test_report_reconciles_with_orders_and_coupons(client):
    cart_id = await new_cart(client, "p1", 2)  # 2 * 99900 = 199800
    await client.post(f"/carts/{cart_id}/checkout")

    cart_id_2 = await new_cart(client, "p2", 1)  # 349900
    await client.post(f"/carts/{cart_id_2}/checkout")

    report = (await client.get("/admin/report")).json()
    assert report["total_orders"] == 2
    assert report["purchased_quantity_by_product"] == {"p1": 2, "p2": 1}
    assert report["gross_revenue_paise"] == 199800 + 349900
    assert report["total_discounts_paise"] == 0
    assert report["net_revenue_paise"] == report["gross_revenue_paise"]
    assert report["coupons_generated"] == 0


async def test_repeated_report_requests_do_not_mutate_state(client):
    cart_id = await new_cart(client, "p1", 1)
    await client.post(f"/carts/{cart_id}/checkout")

    first = (await client.get("/admin/report")).json()
    second = (await client.get("/admin/report")).json()
    assert first == second
