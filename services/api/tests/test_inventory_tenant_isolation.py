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
            "business_name": f"Inventory Business {suffix}",
            "email": f"inventory-{suffix.lower()}@example.com",
            "password": "secure-pass-123",
        },
    )
    session: dict[str, Any] = response.json()
    return session, {"Authorization": f"Bearer {session['access_token']}"}


async def _product(client: AsyncClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "selling_price": "1",
            "unit": "piece",
            "low_stock_threshold": "1",
        },
    )
    return response.json()["product"]


async def test_product_warehouse_movement_and_projection_are_tenant_isolated(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_a, headers_a = await _tenant(client, "A")
    _, headers_b = await _tenant(client, "B")
    product_a = await _product(client, headers_a, "Tenant A Product")
    product_b = await _product(client, headers_b, "Tenant B Product")
    warehouse_b = (
        await client.get("/api/v1/inventory/warehouses/default", headers=headers_b)
    ).json()
    movement_b = await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers_b, "Idempotency-Key": "tenant-b-opening"},
        json={"product_id": product_b["id"], "quantity": "5"},
    )
    assert movement_b.status_code == 201

    cross_product = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers_a, "Idempotency-Key": "cross-product"},
        json={"product_id": product_b["id"], "quantity": "1"},
    )
    assert cross_product.status_code == 404
    assert cross_product.json()["error"]["code"] == "PRODUCT_NOT_FOUND"

    cross_warehouse = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers_a, "Idempotency-Key": "cross-warehouse"},
        json={
            "product_id": product_a["id"],
            "warehouse_id": warehouse_b["id"],
            "quantity": "1",
        },
    )
    assert cross_warehouse.status_code == 404
    assert cross_warehouse.json()["error"]["code"] == "WAREHOUSE_NOT_FOUND"
    assert (await client.get("/api/v1/inventory/history", headers=headers_a)).json()[
        "items"
    ] == []
    stock_a = await client.get("/api/v1/inventory/stock", headers=headers_a)
    assert stock_a.json()["items"][0]["available_quantity"] == "0.000"

    supplied_tenant = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers_a, "Idempotency-Key": str(uuid4())},
        json={
            "product_id": product_a["id"],
            "quantity": "1",
            "tenant_id": session_a["user"]["business"]["id"],
        },
    )
    assert supplied_tenant.status_code == 422
    assert supplied_tenant.json()["error"]["field_errors"]["tenant_id"] == (
        "Tenant id is not accepted. Remove it and try again."
    )

    claims_a = decode_access_token(test_settings, session_a["access_token"])
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_user_id', :value, true)"),
            {"value": str(claims_a.user_id)},
        )
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :value, true)"),
            {"value": str(claims_a.business_id)},
        )
        warehouses = (await connection.execute(text("SELECT id FROM warehouses"))).all()
        movements = (await connection.execute(text("SELECT id FROM stock_movements"))).all()
        balances = (await connection.execute(text("SELECT product_id FROM stock_balances"))).all()
    await engine.dispose()
    assert len(warehouses) == 1
    assert movements == []
    assert balances == []
