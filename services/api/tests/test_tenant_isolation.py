from typing import cast
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.modules.identity.security import create_access_token, decode_access_token


async def _signup(client: AsyncClient, name: str, email: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"business_name": name, "email": email, "password": "secure-pass-123"},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


async def test_businesses_cannot_cross_tenant_boundary(
    client: AsyncClient, test_settings: Settings
) -> None:
    tenant_a = await _signup(client, "Business A", "a@example.com")
    tenant_b = await _signup(client, "Business B", "b@example.com")
    claims_a = decode_access_token(test_settings, str(tenant_a["access_token"]))
    claims_b = decode_access_token(test_settings, str(tenant_b["access_token"]))

    forged_for_b = create_access_token(
        test_settings,
        user_id=claims_a.user_id,
        session_id=claims_a.session_id,
        business_id=claims_b.business_id,
    )
    blocked = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_for_b}"}
    )
    assert blocked.status_code == 401

    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(claims_a.user_id)},
        )
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :business_id, true)"),
            {"business_id": str(claims_b.business_id)},
        )
        visible_to_a = (
            (await connection.execute(text("SELECT id FROM businesses ORDER BY id")))
            .scalars()
            .all()
        )

    await engine.dispose()
    assert visible_to_a == []
    assert UUID(str(tenant_a["user"]["business"]["id"])) == claims_a.business_id  # type: ignore[index]
