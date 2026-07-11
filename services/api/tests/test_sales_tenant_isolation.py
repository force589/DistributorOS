from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.modules.identity.security import decode_access_token


async def _tenant(client: AsyncClient, suffix: str) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Sale Tenant {suffix}",
            "email": f"sale-tenant-{suffix.lower()}@example.com",
            "password": "secure-pass-123",
        },
    )
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def _records(
    client: AsyncClient, headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    customer = (
        await client.post("/api/v1/customers", headers=headers, json={"name": "Tenant Shop"})
    ).json()["customer"]
    product = (
        await client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": "Tenant Product",
                "selling_price": "10",
                "unit": "piece",
                "low_stock_threshold": "1",
            },
        )
    ).json()["product"]
    return customer, product


async def test_sales_and_items_are_isolated_by_rls(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_a, headers_a = await _tenant(client, "A")
    _, headers_b = await _tenant(client, "B")
    customer_a, product_a = await _records(client, headers_a)
    customer_b, product_b = await _records(client, headers_b)
    sale_b = (
        await client.post(
            "/api/v1/sales",
            headers={**headers_b, "Idempotency-Key": "tenant-b-sale"},
            json={
                "customer_id": customer_b["id"],
                "items": [
                    {"product_id": product_b["id"], "quantity": "1", "unit_price": "10"}
                ],
            },
        )
    ).json()["sale"]

    responses = [
        await client.get(f"/api/v1/sales/{sale_b['id']}", headers=headers_a),
        await client.patch(
            f"/api/v1/sales/{sale_b['id']}",
            headers=headers_a,
            json={"customer_id": customer_a["id"]},
        ),
        await client.post(
            f"/api/v1/sales/{sale_b['id']}/post",
            headers={**headers_a, "Idempotency-Key": "cross-post"},
        ),
    ]
    assert all(response.status_code == 404 for response in responses)
    assert all(response.json()["error"]["code"] == "SALE_NOT_FOUND" for response in responses)
    assert (await client.get("/api/v1/sales", headers=headers_a)).json()["items"] == []

    cross_customer = await client.post(
        "/api/v1/sales",
        headers={**headers_a, "Idempotency-Key": "cross-customer"},
        json={
            "customer_id": customer_b["id"],
            "items": [{"product_id": product_a["id"], "quantity": "1", "unit_price": "10"}],
        },
    )
    assert cross_customer.status_code == 404
    cross_product = await client.post(
        "/api/v1/sales",
        headers={**headers_a, "Idempotency-Key": "cross-product"},
        json={
            "customer_id": customer_a["id"],
            "items": [{"product_id": product_b["id"], "quantity": "1", "unit_price": "10"}],
        },
    )
    assert cross_product.status_code == 404
    supplied_tenant = await client.post(
        "/api/v1/sales",
        headers={**headers_a, "Idempotency-Key": str(uuid4())},
        json={
            "tenant_id": session_a["user"]["business"]["id"],
            "customer_id": customer_a["id"],
            "items": [{"product_id": product_a["id"], "quantity": "1", "unit_price": "10"}],
        },
    )
    assert supplied_tenant.status_code == 422

    claims = decode_access_token(test_settings, session_a["access_token"])
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_user_id', :value, true)"),
            {"value": str(claims.user_id)},
        )
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :value, true)"),
            {"value": str(claims.business_id)},
        )
        sales = (await connection.execute(text("SELECT id FROM sales"))).all()
        items = (await connection.execute(text("SELECT id FROM sale_items"))).all()
    await engine.dispose()
    assert sales == []
    assert items == []
