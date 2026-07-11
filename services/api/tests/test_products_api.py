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
    *,
    price: str = "100.00",
    unit: str = "piece",
    threshold: str = "5.000",
    **fields: str | None,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "selling_price": price,
            "unit": unit,
            "low_stock_threshold": threshold,
            **fields,
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body["product"]


async def test_create_read_update_archive_and_restore_product(client: AsyncClient) -> None:
    session, headers = await _signup(client)
    product = await _create(
        client,
        headers,
        "Alphonso Mango Box",
        price="1250.50",
        unit="box",
        threshold="2.500",
        sku="MANGO-BOX-01",
        barcode="8901234567890",
        category="Fruit",
        description="Premium export-grade mangoes",
    )

    assert product["product_code"] == "PROD-000001"
    assert product["selling_price"] == "1250.50"
    assert product["low_stock_threshold"] == "2.500"
    assert product["archived"] is False
    assert product["created_by"] == session["user"]["id"]

    by_id = await client.get(f"/api/v1/products/{product['id']}", headers=headers)
    by_code = await client.get(
        f"/api/v1/products/code/{product['product_code']}", headers=headers
    )
    assert by_id.status_code == by_code.status_code == 200
    assert by_code.json()["name"] == "Alphonso Mango Box"

    updated = await client.patch(
        f"/api/v1/products/{product['id']}",
        headers=headers,
        json={"name": "Alphonso Mango Crate", "selling_price": "1300", "sku": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["product"]["name"] == "Alphonso Mango Crate"
    assert updated.json()["product"]["selling_price"] == "1300.00"
    assert updated.json()["product"]["sku"] is None

    archived = await client.post(
        f"/api/v1/products/{product['id']}/archive", headers=headers
    )
    assert archived.status_code == 200
    assert archived.json()["product"]["archived"] is True
    assert (await client.get("/api/v1/products", headers=headers)).json()["items"] == []
    assert (
        await client.get(
            "/api/v1/products", headers=headers, params={"status": "archived"}
        )
    ).json()["items"][0]["id"] == product["id"]

    restored = await client.post(
        f"/api/v1/products/{product['id']}/restore", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["product"]["archived"] is False


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        (
            {"selling_price": "10", "unit": "piece", "low_stock_threshold": "0"},
            "name",
            "Product name is required.",
        ),
        (
            {"name": "", "selling_price": "10", "unit": "piece", "low_stock_threshold": "0"},
            "name",
            "Product name is required.",
        ),
        (
            {"name": "Price", "selling_price": "-1", "unit": "piece", "low_stock_threshold": "0"},
            "selling_price",
            "Selling price cannot be negative.",
        ),
        (
            {
                "name": "Threshold",
                "selling_price": "1",
                "unit": "piece",
                "low_stock_threshold": "-0.1",
            },
            "low_stock_threshold",
            "Low stock threshold cannot be negative.",
        ),
        (
            {"name": "Unit", "selling_price": "1", "unit": "bucket", "low_stock_threshold": "0"},
            "unit",
            "Choose a supported product unit.",
        ),
        (
            {
                "name": "Price precision",
                "selling_price": "1.999",
                "unit": "kg",
                "low_stock_threshold": "0",
            },
            "selling_price",
            "Selling price can have at most 2 decimal places.",
        ),
        (
            {
                "name": "Threshold precision",
                "selling_price": "1",
                "unit": "kg",
                "low_stock_threshold": "0.0001",
            },
            "low_stock_threshold",
            "Low stock threshold can have at most 3 decimal places.",
        ),
    ],
)
async def test_product_validation_is_actionable(
    client: AsyncClient,
    payload: dict[str, str],
    field: str,
    message: str,
) -> None:
    _, headers = await _signup(client)
    response = await client.post("/api/v1/products", headers=headers, json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["field_errors"][field] == message
    assert "traceback" not in response.text.lower()
    assert "sql" not in response.text.lower()


@pytest.mark.parametrize(
    ("field", "first", "duplicate", "code", "message"),
    [
        (
            "name",
            "Premium Water",
            "premium water",
            "PRODUCT_NAME_ALREADY_EXISTS",
            "A product with this name already exists.",
        ),
        (
            "sku",
            "WATER-01",
            "water-01",
            "PRODUCT_SKU_ALREADY_EXISTS",
            "This SKU already exists.",
        ),
        (
            "barcode",
            "8901234567890",
            "8901234567890",
            "PRODUCT_BARCODE_ALREADY_EXISTS",
            "Barcode already exists.",
        ),
    ],
)
async def test_product_uniqueness_is_tenant_scoped(
    client: AsyncClient,
    field: str,
    first: str,
    duplicate: str,
    code: str,
    message: str,
) -> None:
    _, headers_a = await _signup(client, business="Business A", email="a@example.com")
    first_payload = {field: first} if field != "name" else {}
    original_name = first if field == "name" else f"First {field}"
    await _create(client, headers_a, original_name, **first_payload)

    duplicate_payload = {field: duplicate} if field != "name" else {}
    duplicate_name = duplicate if field == "name" else f"Second {field}"
    response = await client.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": duplicate_name,
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "0",
            **duplicate_payload,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["field_errors"][field] == message

    _, headers_b = await _signup(client, business="Business B", email="b@example.com")
    cross_tenant = await client.post(
        "/api/v1/products",
        headers=headers_b,
        json={
            "name": duplicate_name,
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "0",
            **duplicate_payload,
        },
    )
    assert cross_tenant.status_code == 201
    assert cross_tenant.json()["product"]["product_code"] == "PROD-000001"


async def test_product_search_matches_supported_fields(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    first = await _create(
        client,
        headers,
        "Mineral Water",
        sku="WATER-20L",
        barcode="890100000001",
        category="Beverages",
    )
    second = await _create(client, headers, "Mango Packet", category="Fruit")

    for query, expected in [
        ("mineral", first["id"]),
        (first["product_code"].lower(), first["id"]),
        ("water-20", first["id"]),
        ("000001", first["id"]),
        ("beverage", first["id"]),
        ("fruit", second["id"]),
    ]:
        response = await client.get(
            "/api/v1/products/search", headers=headers, params={"q": query}
        )
        assert response.status_code == 200
        assert expected in [item["id"] for item in response.json()["items"]]

    blank = await client.get(
        "/api/v1/products/search", headers=headers, params={"q": "   "}
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["field_errors"]["q"] == (
        "Enter a product name, code, SKU, barcode, or category."
    )


async def test_product_cursor_pagination_and_all_sorts(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    products = [("Delta", "40"), ("Alpha", "10"), ("Charlie", "30"), ("Bravo", "20")]
    for name, price in products:
        await _create(client, headers, name, price=price)

    first = await client.get(
        "/api/v1/products", headers=headers, params={"sort": "name_asc", "limit": 2}
    )
    assert [item["name"] for item in first.json()["items"]] == ["Alpha", "Bravo"]
    assert first.json()["has_more"] is True
    second = await client.get(
        "/api/v1/products",
        headers=headers,
        params={
            "sort": "name_asc",
            "limit": 2,
            "cursor": first.json()["next_cursor"],
        },
    )
    assert [item["name"] for item in second.json()["items"]] == ["Charlie", "Delta"]

    expectations = {
        "name_desc": ["Delta", "Charlie", "Bravo", "Alpha"],
        "price_asc": ["Alpha", "Bravo", "Charlie", "Delta"],
        "price_desc": ["Delta", "Charlie", "Bravo", "Alpha"],
        "newest": ["Bravo", "Charlie", "Alpha", "Delta"],
        "oldest": ["Delta", "Alpha", "Charlie", "Bravo"],
    }
    for sort, names in expectations.items():
        response = await client.get(
            "/api/v1/products", headers=headers, params={"sort": sort}
        )
        assert [item["name"] for item in response.json()["items"]] == names

    invalid_cursor = await client.get(
        "/api/v1/products",
        headers=headers,
        params={"sort": "price_asc", "cursor": first.json()["next_cursor"]},
    )
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["error"]["code"] == "INVALID_PRODUCT_CURSOR"


async def test_product_filters(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    active = await _create(client, headers, "Active Product")
    archived = await _create(client, headers, "Archived Product")
    await client.post(f"/api/v1/products/{archived['id']}/archive", headers=headers)

    active_list = await client.get(
        "/api/v1/products", headers=headers, params={"status": "active"}
    )
    archived_list = await client.get(
        "/api/v1/products", headers=headers, params={"status": "archived"}
    )
    all_list = await client.get(
        "/api/v1/products", headers=headers, params={"status": "all"}
    )
    assert [item["id"] for item in active_list.json()["items"]] == [active["id"]]
    assert [item["id"] for item in archived_list.json()["items"]] == [archived["id"]]
    assert {item["id"] for item in all_list.json()["items"]} == {
        active["id"],
        archived["id"],
    }


async def test_concurrent_product_submit_creates_only_one(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    payload = {
        "name": "One Tap Product",
        "selling_price": "10",
        "unit": "piece",
        "low_stock_threshold": "0",
    }
    responses = await asyncio.gather(
        client.post("/api/v1/products", headers=headers, json=payload),
        client.post("/api/v1/products", headers=headers, json=payload),
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    product_list = await client.get("/api/v1/products", headers=headers)
    assert [item["name"] for item in product_list.json()["items"]] == ["One Tap Product"]


async def test_concurrent_product_codes_are_unique_and_sequential(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/products",
                headers=headers,
                json={
                    "name": f"Concurrent Product {number}",
                    "selling_price": str(number),
                    "unit": "piece",
                    "low_stock_threshold": "0",
                },
            )
            for number in range(1, 4)
        ]
    )
    assert all(response.status_code == 201 for response in responses)
    assert {response.json()["product"]["product_code"] for response in responses} == {
        "PROD-000001",
        "PROD-000002",
        "PROD-000003",
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/products", None),
        ("GET", f"/api/v1/products/{uuid4()}", None),
        ("GET", "/api/v1/products/code/PROD-000001", None),
        (
            "POST",
            "/api/v1/products",
            {
                "name": "Unauthorized",
                "selling_price": "1",
                "unit": "piece",
                "low_stock_threshold": "0",
            },
        ),
        ("PATCH", f"/api/v1/products/{uuid4()}", {"name": "Unauthorized"}),
        ("POST", f"/api/v1/products/{uuid4()}/archive", None),
        ("POST", f"/api/v1/products/{uuid4()}/restore", None),
        ("GET", "/api/v1/products/search?q=product", None),
    ],
)
async def test_every_product_endpoint_requires_authentication(
    client: AsyncClient,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    response = await client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
