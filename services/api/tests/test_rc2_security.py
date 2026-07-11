import asyncio
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.core.database import set_internal_maintenance_context
from distributoros.main import create_app


async def _signup(client: AsyncClient, *, platform: str = "android") -> dict[str, Any]:
    headers = {"X-Client-Platform": platform}
    if platform == "web":
        headers["Origin"] = "http://localhost:8081"
    response = await client.post(
        "/api/v1/auth/signup",
        headers=headers,
        json={
            "business_name": "RC2 Security",
            "email": "rc2-security@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def _reset_token(settings: Settings) -> str:
    assert settings.database_admin_url
    engine = create_async_engine(settings.database_admin_url)
    try:
        async with engine.connect() as connection:
            await set_internal_maintenance_context(connection)
            reset_url = await connection.scalar(
                text(
                    "SELECT payload->>'reset_url' FROM outbox_events "
                    "WHERE event_type = 'identity.password_reset_requested' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            )
        assert reset_url
        return parse_qs(urlparse(str(reset_url)).query)["token"][0]
    finally:
        await engine.dispose()


async def test_password_reset_is_enumeration_safe_and_revokes_sessions(
    client: AsyncClient, test_settings: Settings
) -> None:
    session = await _signup(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    known = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "rc2-security@example.com"}
    )
    unknown = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()

    token = await _reset_token(test_settings)
    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "new-secure-pass-456"},
    )
    assert reset.status_code == 200, reset.text
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rc2-security@example.com", "password": "secure-pass-123"},
    )
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rc2-security@example.com", "password": "new-secure-pass-456"},
    )
    replay = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "another-secure-pass-789"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert replay.status_code == 422
    assert replay.json()["error"]["code"] == "PASSWORD_RESET_LINK_INVALID"


async def test_change_password_validates_current_password_and_revokes_session(
    client: AsyncClient,
) -> None:
    session = await _signup(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    wrong = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": "new-pass-456"},
    )
    assert wrong.status_code == 422
    assert wrong.json()["error"]["field_errors"]["current_password"]

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "secure-pass-123", "new_password": "new-pass-456"},
    )
    assert changed.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401


async def test_concurrent_web_refreshes_both_succeed_and_missing_cookie_expires(
    client: AsyncClient,
) -> None:
    await _signup(client, platform="web")
    cookie = client.cookies.get("distributoros_refresh")
    assert cookie
    headers = {
        "X-Client-Platform": "web",
        "Origin": "http://localhost:8081",
        "Cookie": f"distributoros_refresh={cookie}",
    }

    async def refresh() -> int:
        response = await client.post("/api/v1/auth/refresh", headers=headers, json={})
        return response.status_code

    assert sorted(await asyncio.gather(refresh(), refresh())) == [200, 200]
    client.cookies.clear()
    missing = await client.post(
        "/api/v1/auth/refresh",
        headers={"X-Client-Platform": "web", "Origin": "http://localhost:8081"},
        json={},
    )
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_rate_limit_and_malformed_json_are_stable(
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(
        update={"rate_limit_enabled": True, "login_rate_limit": 2, "signup_rate_limit": 10}
    )
    app = create_app(settings)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as limited:
            await _signup(limited)
            for expected in (401, 401, 429):
                response = await limited.post(
                    "/api/v1/auth/login",
                    json={"email": "rc2-security@example.com", "password": "wrong-pass"},
                )
                assert response.status_code == expected, response.text
            assert response.headers["Retry-After"]

            malformed = await limited.post(
                "/api/v1/auth/login",
                content=b'{"email":',
                headers={"Content-Type": "application/json"},
            )
            assert malformed.status_code == 422
            assert malformed.json()["error"]["field_errors"] == {
                "request": "The request body is not valid JSON. Check its syntax and try again."
            }
    finally:
        await app.state.database.dispose()
