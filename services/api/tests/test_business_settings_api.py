from typing import Any
from uuid import uuid4

from httpx import AsyncClient


async def _signup(
    client: AsyncClient, suffix: str
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Settings {suffix}",
            "email": f"settings-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def test_business_settings_defaults_update_and_auth_readback(client: AsyncClient) -> None:
    signup, headers = await _signup(client, "primary")
    assert signup["user"]["business"] == {
        "id": signup["user"]["business"]["id"],
        "business_name": "Settings primary",
        "currency": "INR",
        "language": "en",
        "theme": "system",
        "timezone": "Asia/Kolkata",
    }

    defaults = await client.get("/api/v1/business/settings", headers=headers)
    assert defaults.status_code == 200, defaults.text
    assert defaults.json() == {
        "business_name": "Settings primary",
        "currency": "INR",
        "language": "en",
        "theme": "system",
        "timezone": "Asia/Kolkata",
    }

    updated = await client.patch(
        "/api/v1/business/settings",
        headers=headers,
        json={
            "business_name": "Kerala Distribution",
            "currency": "AED",
            "language": "ml",
            "theme": "dark",
            "timezone": "Asia/Dubai",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {
        "business_name": "Kerala Distribution",
        "currency": "AED",
        "language": "ml",
        "theme": "dark",
        "timezone": "Asia/Dubai",
    }

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["user"]["business"]["currency"] == "AED"
    assert me.json()["user"]["business"]["language"] == "ml"
    assert me.json()["user"]["business"]["theme"] == "dark"
    assert me.json()["user"]["business"]["timezone"] == "Asia/Dubai"

    dashboard = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["timezone"] == "Asia/Dubai"


async def test_business_settings_validation_and_tenant_isolation(client: AsyncClient) -> None:
    _, headers_a = await _signup(client, "tenant-a")
    _, headers_b = await _signup(client, "tenant-b")

    invalid = await client.patch(
        "/api/v1/business/settings",
        headers=headers_a,
        json={"currency": "BTC"},
    )
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "currency" in invalid.json()["error"]["field_errors"]

    invalid_timezone = await client.patch(
        "/api/v1/business/settings",
        headers=headers_a,
        json={"timezone": "Not/A-Timezone"},
    )
    assert invalid_timezone.status_code == 422, invalid_timezone.text
    assert invalid_timezone.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "timezone" in invalid_timezone.json()["error"]["field_errors"]

    changed = await client.patch(
        "/api/v1/business/settings",
        headers=headers_a,
        json={"currency": "USD"},
    )
    assert changed.status_code == 200, changed.text
    tenant_b = await client.get("/api/v1/business/settings", headers=headers_b)
    assert tenant_b.status_code == 200, tenant_b.text
    assert tenant_b.json()["currency"] == "INR"

    unauthorized = await client.get("/api/v1/business/settings")
    assert unauthorized.status_code == 401


async def test_currency_change_is_blocked_after_financial_history(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "currency-lock")
    customer_response = await client.post(
        "/api/v1/customers", headers=headers, json={"name": "Currency Customer"}
    )
    assert customer_response.status_code == 201, customer_response.text
    customer = customer_response.json()["customer"]
    product_response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Currency Product",
            "selling_price": "100",
            "unit": "piece",
            "low_stock_threshold": "1",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()["product"]
    stock = await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product["id"], "quantity": "5"},
    )
    assert stock.status_code == 201, stock.text
    sale_response = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "customer_id": customer["id"],
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": "1",
                    "unit_price": "100",
                }
            ],
        },
    )
    assert sale_response.status_code == 201, sale_response.text
    sale = sale_response.json()["sale"]
    posted = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert posted.status_code == 200, posted.text

    blocked = await client.patch(
        "/api/v1/business/settings",
        headers=headers,
        json={"currency": "USD"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"] == {
        "code": "CURRENCY_CHANGE_RESTRICTED",
        "message": (
            "Currency cannot be changed after financial transactions exist. "
            "Keep the current currency to preserve historical amounts."
        ),
        "field_errors": {
            "currency": (
                "This business already has financial history. "
                "Currency conversion is not supported."
            )
        },
        "request_id": blocked.json()["error"]["request_id"],
    }

    settings = await client.get("/api/v1/business/settings", headers=headers)
    assert settings.json()["currency"] == "INR"
