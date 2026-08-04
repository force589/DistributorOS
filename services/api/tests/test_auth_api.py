import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.core.database import set_internal_maintenance_context
from distributoros.main import create_app

SIGNUP = {
    "business_name": "Fresh Route Distributors",
    "email": "owner@example.com",
    "password": "secure-pass-123",
}


async def test_signup_login_refresh_logout_and_protected_route(client: AsyncClient) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json=SIGNUP,
        headers={"X-Client-Platform": "android"},
    )
    assert signup.status_code == 201
    signup_body = signup.json()
    assert signup_body["refresh_token"]
    assert signup_body["user"]["business"]["business_name"] == SIGNUP["business_name"]

    access_token = signup_body["access_token"]
    protected = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert protected.status_code == 200
    assert protected.json()["user"]["email"] == SIGNUP["email"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": signup_body["refresh_token"]},
        headers={"X-Client-Platform": "android"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != signup_body["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert logout.status_code == 200
    assert logout.json()["message"] == "You have been signed out successfully."

    after_logout = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP["email"], "password": SIGNUP["password"]},
    )
    assert login.status_code == 200
    assert login.json()["user"]["business"]["business_name"] == SIGNUP["business_name"]


async def test_login_does_not_reveal_which_credential_is_wrong(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/signup", json=SIGNUP)

    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP["email"], "password": "wrong-password"},
    )
    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["message"] == (
        "Incorrect email or password. Check your details and try again."
    )
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        (
            {"email": "invalid", "password": "secure-pass-123"},
            "email",
            "Please enter a valid email.",
        ),
        (
            {"email": "owner@example.com", "password": "short"},
            "password",
            "Password must contain at least 8 characters.",
        ),
        ({"email": "", "password": "secure-pass-123"}, "email", "Email is required."),
        ({"email": "owner@example.com", "password": ""}, "password", "Password is required."),
    ],
)
async def test_login_validation_is_actionable(
    client: AsyncClient,
    payload: dict[str, str],
    field: str,
    message: str,
) -> None:
    response = await client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["field_errors"][field] == message
    assert "traceback" not in response.text.lower()
    assert "sql" not in response.text.lower()


async def test_signup_validation_and_duplicate_email_are_actionable(client: AsyncClient) -> None:
    invalid = await client.post(
        "/api/v1/auth/signup",
        json={"business_name": "", "email": "invalid", "password": "short"},
    )
    assert invalid.status_code == 422
    errors = invalid.json()["error"]["field_errors"]
    assert errors["business_name"] == "Business name is required."
    assert errors["email"] == "Please enter a valid email."
    assert errors["password"] == "Password must contain at least 8 characters."

    assert (await client.post("/api/v1/auth/signup", json=SIGNUP)).status_code == 201
    duplicate = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["field_errors"]["email"] == (
        "This email is already registered."
    )


async def test_frontend_cannot_supply_business_id(client: AsyncClient) -> None:
    manipulated = await client.post(
        "/api/v1/auth/signup",
        json={**SIGNUP, "business_id": "00000000-0000-0000-0000-000000000001"},
    )

    assert manipulated.status_code == 422
    assert manipulated.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_web_session_uses_http_only_cookie(client: AsyncClient) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json=SIGNUP,
        headers={"X-Client-Platform": "web", "Origin": "http://localhost:8081"},
    )
    assert signup.status_code == 201
    assert signup.json()["refresh_token"] is None
    assert "HttpOnly" in signup.headers["set-cookie"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={"X-Client-Platform": "web", "Origin": "http://localhost:8081"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] is None


async def test_preview_web_session_cookie_is_cross_site_safe(test_settings: Settings) -> None:
    preview_settings = test_settings.model_copy(
        update={
            "environment": "preview",
            "cors_origins": ["https://distributoros.pages.dev"],
            "cookie_secure": True,
            "cookie_samesite": "lax",
            "password_reset_url_base": "https://distributoros.pages.dev/reset-password",
        },
    )
    application = create_app(preview_settings)
    try:
        transport = ASGITransport(app=application, raise_app_exceptions=False)
        async with AsyncClient(
            transport=transport,
            base_url="https://distributoros-api.onrender.com",
        ) as preview_client:
            signup = await preview_client.post(
                "/api/v1/auth/signup",
                json=SIGNUP,
                headers={
                    "X-Client-Platform": "web",
                    "Origin": "https://distributoros.pages.dev",
                },
            )

            assert signup.status_code == 201
            assert signup.json()["refresh_token"] is None
            cookie = signup.headers["set-cookie"]
            assert "HttpOnly" in cookie
            assert "Secure" in cookie
            assert "SameSite=none" in cookie

            refreshed = await preview_client.post(
                "/api/v1/auth/refresh",
                json={},
                headers={
                    "X-Client-Platform": "web",
                    "Origin": "https://distributoros.pages.dev",
                },
            )

            assert refreshed.status_code == 200
            assert refreshed.json()["refresh_token"] is None
    finally:
        await application.state.database.dispose()


async def test_api_errors_have_request_ids_and_friendly_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/not-a-real-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_registration_persists_business_user_and_membership(
    client: AsyncClient, test_settings: Settings
) -> None:
    response = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert response.status_code == 201
    body = response.json()
    user_id = body["user"]["id"]
    business_id = body["user"]["business"]["id"]

    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    async with engine.connect() as connection:
        await set_internal_maintenance_context(connection)
        counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM businesses WHERE id = :business_id),
                      (SELECT count(*) FROM users WHERE id = :user_id),
                      (SELECT count(*) FROM memberships
                       WHERE business_id = :business_id AND user_id = :user_id)
                    """
                ),
                {"business_id": business_id, "user_id": user_id},
            )
        ).one()
    await engine.dispose()

    assert tuple(counts) == (1, 1, 1)
