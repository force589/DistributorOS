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


async def test_customer_ids_codes_and_rls_cannot_cross_tenants(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_a, headers_a = await _tenant(client, "A")
    _, headers_b = await _tenant(client, "B")
    created = await client.post(
        "/api/v1/customers",
        headers=headers_b,
        json={"name": "Business B Customer"},
    )
    assert created.status_code == 201
    customer_b = created.json()["customer"]

    by_id = await client.get(f"/api/v1/customers/{customer_b['id']}", headers=headers_a)
    by_code = await client.get(
        f"/api/v1/customers/code/{customer_b['customer_code']}", headers=headers_a
    )
    update = await client.patch(
        f"/api/v1/customers/{customer_b['id']}",
        headers=headers_a,
        json={"name": "Stolen"},
    )
    archive = await client.post(
        f"/api/v1/customers/{customer_b['id']}/archive", headers=headers_a
    )
    assert {by_id.status_code, by_code.status_code, update.status_code, archive.status_code} == {
        404
    }
    assert all(
        response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"
        for response in (by_id, by_code, update, archive)
    )

    list_a = await client.get("/api/v1/customers", headers=headers_a)
    search_a = await client.get(
        "/api/v1/customers/search", headers=headers_a, params={"q": "Business B"}
    )
    assert list_a.json()["items"] == search_a.json()["items"] == []

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
        visible = (await connection.execute(text("SELECT id FROM customers"))).scalars().all()
    await engine.dispose()
    assert visible == []


async def test_client_supplied_tenant_identifiers_are_rejected(client: AsyncClient) -> None:
    session, headers = await _tenant(client, "A")
    tenant_id = session["user"]["business"]["id"]

    response = await client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Manipulated", "tenant_id": tenant_id},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["field_errors"]["tenant_id"] == (
        "Tenant id is not accepted. Remove it and try again."
    )
