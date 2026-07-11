import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from distributoros.core.config import Settings
from distributoros.modules.identity.security import decode_access_token

SIGNUP = {
    "business_name": "Security Test Business",
    "email": "security@example.com",
    "password": "secure-pass-123",
}


async def _signup(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/signup",
        json=SIGNUP,
        headers={"X-Client-Platform": "android"},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


async def test_missing_invalid_modified_and_expired_access_tokens_are_rejected(
    client: AsyncClient, test_settings: Settings
) -> None:
    session = await _signup(client)
    access_token = str(session["access_token"])
    claims = decode_access_token(test_settings, access_token)
    expired = jwt.encode(
        {
            "sub": str(claims.user_id),
            "sid": str(claims.session_id),
            "tid": str(claims.business_id),
            "type": "access",
            "iss": test_settings.jwt_issuer,
            "aud": test_settings.jwt_audience,
            "iat": datetime.now(UTC) - timedelta(minutes=10),
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        test_settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    header, payload, signature = access_token.split(".")
    tampered_signature = f"{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
    modified = ".".join([header, payload, tampered_signature])

    cases = [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": f"Bearer {modified}"},
        {"Authorization": f"Bearer {expired}"},
    ]
    for headers in cases:
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert "traceback" not in response.text.lower()


async def test_rotated_refresh_token_cannot_be_replayed(client: AsyncClient) -> None:
    session = await _signup(client)
    original_refresh = str(session["refresh_token"])
    first = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
        headers={"X-Client-Platform": "android"},
    )
    assert first.status_code == 200

    replay = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
        headers={"X-Client-Platform": "android"},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_concurrent_refresh_allows_exactly_one_rotation(client: AsyncClient) -> None:
    session = await _signup(client)
    original_refresh = str(session["refresh_token"])

    async def refresh() -> Response:
        return await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh},
            headers={"X-Client-Platform": "android"},
        )

    responses = await asyncio.gather(refresh(), refresh())
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 401]


async def test_revoked_session_cannot_be_reused(client: AsyncClient) -> None:
    session = await _signup(client)
    access_token = str(session["access_token"])
    refresh_token = str(session["refresh_token"])

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout.status_code == 200

    access_reuse = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    refresh_reuse = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={"X-Client-Platform": "android"},
    )
    assert access_reuse.status_code == 401
    assert refresh_reuse.status_code == 401


async def test_unhandled_errors_never_expose_internal_details(
    app: FastAPI, test_settings: Settings
) -> None:
    del test_settings

    async def fail_safely() -> None:
        raise RuntimeError("database-password-and-internal-stack")

    app.add_api_route("/test/unhandled", fail_safely, methods=["GET"])
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/test/unhandled")

    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "INTERNAL_SERVER_ERROR"
    assert body["request_id"]
    assert "database-password" not in response.text
    assert "traceback" not in response.text.lower()
