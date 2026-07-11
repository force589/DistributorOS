from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.modules.identity.security import decode_access_token


async def _tenant(client: AsyncClient, suffix: str) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Business {suffix}",
            "email": f"{suffix.lower()}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def test_product_ids_codes_and_rls_cannot_cross_tenants(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_a, headers_a = await _tenant(client, "A")
    _, headers_b = await _tenant(client, "B")
    created = await client.post(
        "/api/v1/products",
        headers=headers_b,
        json={
            "name": "Business B Product",
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "0",
        },
    )
    assert created.status_code == 201
    product_b = created.json()["product"]

    responses = [
        await client.get(f"/api/v1/products/{product_b['id']}", headers=headers_a),
        await client.get(
            f"/api/v1/products/code/{product_b['product_code']}", headers=headers_a
        ),
        await client.patch(
            f"/api/v1/products/{product_b['id']}",
            headers=headers_a,
            json={"name": "Stolen"},
        ),
        await client.post(
            f"/api/v1/products/{product_b['id']}/archive", headers=headers_a
        ),
    ]
    assert all(response.status_code == 404 for response in responses)
    assert all(
        response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
        for response in responses
    )
    assert (await client.get("/api/v1/products", headers=headers_a)).json()["items"] == []

    claims_a = decode_access_token(test_settings, session_a["access_token"])
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(claims_a.user_id)},
        )
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(claims_a.business_id)},
        )
        visible = (await connection.execute(text("SELECT id FROM products"))).scalars().all()
    await engine.dispose()
    assert visible == []


async def test_client_cannot_supply_product_tenant_id(client: AsyncClient) -> None:
    session, headers = await _tenant(client, "A")
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Manipulated",
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "0",
            "tenant_id": session["user"]["business"]["id"],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["field_errors"]["tenant_id"] == (
        "Tenant id is not accepted. Remove it and try again."
    )
