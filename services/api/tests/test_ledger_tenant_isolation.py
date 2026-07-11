from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings


async def _business(client: AsyncClient, suffix: str) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Ledger Tenant {suffix}",
            "email": f"ledger-tenant-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def _posted_sale(
    client: AsyncClient, headers: dict[str, str], suffix: str
) -> tuple[str, str]:
    customer_response = await client.post(
        "/api/v1/customers", headers=headers, json={"name": f"Ledger Customer {suffix}"}
    )
    customer = customer_response.json()["customer"]
    product_response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": f"Ledger Product {suffix}",
            "selling_price": "15",
            "unit": "piece",
            "low_stock_threshold": "0",
        },
    )
    product = product_response.json()["product"]
    await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": f"stock-{suffix}"},
        json={"product_id": product["id"], "quantity": "10"},
    )
    sale_response = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": f"sale-{suffix}"},
        json={
            "customer_id": customer["id"],
            "items": [
                {"product_id": product["id"], "quantity": "1", "unit_price": "15"}
            ],
        },
    )
    sale = sale_response.json()["sale"]
    posted = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": f"post-{suffix}"},
    )
    assert posted.status_code == 200, posted.text
    return customer["id"], sale["id"]


async def test_ledger_api_and_rls_reject_cross_tenant_access(
    client: AsyncClient, test_settings: Settings
) -> None:
    _, headers_a = await _business(client, "a")
    business_b, headers_b = await _business(client, "b")
    customer_a, _ = await _posted_sale(client, headers_a, "a")
    customer_b, _ = await _posted_sale(client, headers_b, "b")

    for path in (
        f"/api/v1/customers/{customer_a}/ledger",
        f"/api/v1/customers/{customer_a}/financial-summary",
    ):
        cross = await client.get(path, headers=headers_b)
        assert cross.status_code == 404
        assert cross.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"

    own = await client.get(f"/api/v1/customers/{customer_b}/ledger", headers=headers_b)
    assert own.status_code == 200
    assert len(own.json()["items"]) == 1

    engine = create_async_engine(test_settings.database_url)
    async with engine.connect() as connection, connection.begin():
        await connection.execute(
            text("SELECT set_config('app.current_user_id', :value, true)"),
            {"value": str(business_b["user"]["id"])},
        )
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :value, true)"),
            {"value": str(business_b["user"]["business"]["id"])},
        )
        ledger_tenants = {
            str(tenant_id)
            for tenant_id in (
                await connection.execute(
                    text("SELECT tenant_id FROM customer_ledger_entries")
                )
            ).scalars()
        }
        projection_tenants = {
            str(tenant_id)
            for tenant_id in (
                await connection.execute(
                    text("SELECT tenant_id FROM customer_balance_projections")
                )
            ).scalars()
        }
        assert ledger_tenants == {business_b["user"]["business"]["id"]}
        assert projection_tenants == {business_b["user"]["business"]["id"]}
    await engine.dispose()
