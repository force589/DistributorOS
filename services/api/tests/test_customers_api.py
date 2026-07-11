import asyncio
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _signup(
    client: AsyncClient, *, business: str = "Fresh Route", email: str = "owner@example.com"
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": business,
            "email": email,
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def _create(
    client: AsyncClient,
    headers: Mapping[str, str],
    name: str,
    **fields: str | None,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": name, **fields},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body["customer"]


async def test_create_read_update_archive_and_restore_customer(client: AsyncClient) -> None:
    session, headers = await _signup(client)
    customer = await _create(
        client,
        headers,
        "Mango Corner",
        phone="+91 98765 43210",
        email="orders@mangocorner.in",
        city="Kochi",
    )

    assert customer["customer_code"] == "CUST-000001"
    assert customer["archived"] is False
    assert customer["created_by"] == session["user"]["id"]
    assert customer["updated_by"] == session["user"]["id"]

    by_id = await client.get(f"/api/v1/customers/{customer['id']}", headers=headers)
    by_code = await client.get(
        f"/api/v1/customers/code/{customer['customer_code']}", headers=headers
    )
    assert by_id.status_code == by_code.status_code == 200
    assert by_code.json()["name"] == "Mango Corner"

    updated = await client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"name": "Mango Corner Wholesale", "phone": "9876543210", "email": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["customer"]["name"] == "Mango Corner Wholesale"
    assert updated.json()["customer"]["email"] is None
    assert updated.json()["message"] == "Customer updated successfully."

    archived = await client.post(
        f"/api/v1/customers/{customer['id']}/archive", headers=headers
    )
    assert archived.status_code == 200
    assert archived.json()["customer"]["archived"] is True

    normal_list = await client.get("/api/v1/customers", headers=headers)
    archived_list = await client.get(
        "/api/v1/customers", headers=headers, params={"status": "archived"}
    )
    assert normal_list.json()["items"] == []
    assert [item["id"] for item in archived_list.json()["items"]] == [customer["id"]]

    restored = await client.post(
        f"/api/v1/customers/{customer['id']}/restore", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["customer"]["archived"] is False


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"name": ""}, "name", "Customer name is required."),
        ({"name": "x" * 161}, "name", "Customer name must not exceed 160 characters."),
        (
            {"name": "Invalid Email", "email": "not-an-email"},
            "email",
            "Please enter a valid email address.",
        ),
        (
            {"name": "Invalid Phone", "phone": "12-ab"},
            "phone",
            "Please enter a valid phone number.",
        ),
    ],
)
async def test_customer_validation_is_field_specific(
    client: AsyncClient,
    payload: dict[str, str],
    field: str,
    message: str,
) -> None:
    _, headers = await _signup(client)
    response = await client.post("/api/v1/customers", headers=headers, json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == message
    assert error["field_errors"][field] == message
    assert "traceback" not in response.text.lower()
    assert "sql" not in response.text.lower()


async def test_duplicate_names_are_prevented_only_within_a_tenant(
    client: AsyncClient,
) -> None:
    _, headers_a = await _signup(client, business="Business A", email="a@example.com")
    await _create(client, headers_a, "Same Name")

    duplicate = await client.post(
        "/api/v1/customers", headers=headers_a, json={"name": "Same Name"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == {
        "code": "CUSTOMER_NAME_ALREADY_EXISTS",
        "message": "A customer with this name already exists.",
        "request_id": duplicate.headers["X-Request-ID"],
        "field_errors": {"name": "A customer with this name already exists."},
    }

    case_variant = await client.post(
        "/api/v1/customers", headers=headers_a, json={"name": "same name"}
    )
    assert case_variant.status_code == 409

    original = await client.get("/api/v1/customers", headers=headers_a)
    assert original.json()["items"][0]["name"] == "Same Name"

    _, headers_b = await _signup(client, business="Business B", email="b@example.com")
    cross_tenant = await client.post(
        "/api/v1/customers", headers=headers_b, json={"name": "Same Name"}
    )
    assert cross_tenant.status_code == 201
    assert cross_tenant.json()["customer"]["customer_code"] == "CUST-000001"


async def test_customer_search_matches_supported_fields(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    first = await _create(
        client,
        headers,
        "Al Noor Fruits",
        phone="9876543210",
        email="buyer@alnoor.in",
    )
    second = await _create(client, headers, "Blue Water Supply", phone="9123456780")

    for query, expected_id in [
        ("noor", first["id"]),
        ("6543", first["id"]),
        ("buyer@", first["id"]),
        (first["customer_code"].lower(), first["id"]),
        ("water", second["id"]),
    ]:
        response = await client.get(
            "/api/v1/customers/search",
            headers=headers,
            params={"q": query},
        )
        assert response.status_code == 200
        assert expected_id in [item["id"] for item in response.json()["items"]]

    blank = await client.get(
        "/api/v1/customers/search", headers=headers, params={"q": "   "}
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["field_errors"]["q"] == (
        "Enter a customer name, phone number, email, or customer code."
    )


async def test_cursor_pagination_and_sorting_are_stable(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    for name in ["Delta", "Alpha", "Charlie", "Bravo", "Echo"]:
        await _create(client, headers, name)

    first_page = await client.get(
        "/api/v1/customers",
        headers=headers,
        params={"sort": "name_asc", "limit": 2},
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert [item["name"] for item in first_body["items"]] == ["Alpha", "Bravo"]
    assert first_body["has_more"] is True
    assert first_body["page_size"] == 2
    assert first_body["next_cursor"]

    second_page = await client.get(
        "/api/v1/customers",
        headers=headers,
        params={
            "sort": "name_asc",
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
    )
    assert [item["name"] for item in second_page.json()["items"]] == ["Charlie", "Delta"]

    descending = await client.get(
        "/api/v1/customers", headers=headers, params={"sort": "name_desc"}
    )
    assert [item["name"] for item in descending.json()["items"]] == [
        "Echo",
        "Delta",
        "Charlie",
        "Bravo",
        "Alpha",
    ]

    newest = await client.get(
        "/api/v1/customers", headers=headers, params={"sort": "newest"}
    )
    oldest = await client.get(
        "/api/v1/customers", headers=headers, params={"sort": "oldest"}
    )
    assert [item["name"] for item in newest.json()["items"]] == [
        "Echo",
        "Bravo",
        "Charlie",
        "Alpha",
        "Delta",
    ]
    assert [item["name"] for item in oldest.json()["items"]] == [
        "Delta",
        "Alpha",
        "Charlie",
        "Bravo",
        "Echo",
    ]

    invalid_reuse = await client.get(
        "/api/v1/customers",
        headers=headers,
        params={"sort": "newest", "cursor": first_body["next_cursor"]},
    )
    assert invalid_reuse.status_code == 422
    assert invalid_reuse.json()["error"]["code"] == "INVALID_CUSTOMER_CURSOR"


async def test_all_active_and_archived_filters(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    active = await _create(client, headers, "Active Customer")
    archived = await _create(client, headers, "Archived Customer")
    await client.post(f"/api/v1/customers/{archived['id']}/archive", headers=headers)

    active_response = await client.get(
        "/api/v1/customers", headers=headers, params={"status": "active"}
    )
    archived_response = await client.get(
        "/api/v1/customers", headers=headers, params={"status": "archived"}
    )
    all_response = await client.get(
        "/api/v1/customers", headers=headers, params={"status": "all"}
    )

    assert [item["id"] for item in active_response.json()["items"]] == [active["id"]]
    assert [item["id"] for item in archived_response.json()["items"]] == [archived["id"]]
    assert {item["id"] for item in all_response.json()["items"]} == {
        active["id"],
        archived["id"],
    }


async def test_concurrent_double_submit_creates_only_one_customer(client: AsyncClient) -> None:
    _, headers = await _signup(client)

    responses = await asyncio.gather(
        client.post("/api/v1/customers", headers=headers, json={"name": "One Tap"}),
        client.post("/api/v1/customers", headers=headers, json={"name": "One Tap"}),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    customer_list = await client.get("/api/v1/customers", headers=headers)
    assert [item["name"] for item in customer_list.json()["items"]] == ["One Tap"]


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/customers", None),
        ("GET", f"/api/v1/customers/{uuid4()}", None),
        ("GET", "/api/v1/customers/code/CUST-000001", None),
        ("POST", "/api/v1/customers", {"name": "Unauthorized"}),
        ("PATCH", f"/api/v1/customers/{uuid4()}", {"name": "Unauthorized"}),
        ("POST", f"/api/v1/customers/{uuid4()}/archive", None),
        ("POST", f"/api/v1/customers/{uuid4()}/restore", None),
        ("GET", "/api/v1/customers/search?q=customer", None),
    ],
)
async def test_every_customer_endpoint_requires_authentication(
    client: AsyncClient,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    response = await client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
