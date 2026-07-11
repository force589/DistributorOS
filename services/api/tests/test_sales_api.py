import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.core.database import set_internal_maintenance_context


async def _signup(
    client: AsyncClient, suffix: str = "sales"
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Sales {suffix}",
            "email": f"sales-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def _customer(
    client: AsyncClient, headers: dict[str, str], name: str
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/customers", headers=headers, json={"name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()["customer"]


async def _product(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    price: str = "10",
    unit: str = "piece",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "selling_price": price,
            "unit": unit,
            "low_stock_threshold": "1",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]


async def _stock(
    client: AsyncClient,
    headers: dict[str, str],
    product_id: str,
    quantity: str,
) -> None:
    response = await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product_id, "quantity": quantity},
    )
    assert response.status_code == 201, response.text


def _line(product: dict[str, Any], quantity: str = "1", price: str | None = None) -> dict[str, str]:
    return {
        "product_id": product["id"],
        "quantity": quantity,
        "unit_price": price or product["selling_price"],
    }


async def _sale(
    client: AsyncClient,
    headers: dict[str, str],
    customer: dict[str, Any],
    items: list[dict[str, str]],
    *,
    key: str | None = None,
) -> Any:
    return await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json={"customer_id": customer["id"], "items": items},
    )


async def test_create_edit_and_read_draft(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    first_customer = await _customer(client, headers, "First Shop")
    second_customer = await _customer(client, headers, "Second Shop")
    mango = await _product(client, headers, "Mango", price="12.50", unit="kg")
    water = await _product(client, headers, "Water", price="20", unit="litre")

    created = await _sale(
        client,
        headers,
        first_customer,
        [_line(mango, "2.500"), _line(water, "3")],
    )
    assert created.status_code == 201, created.text
    draft = created.json()["sale"]
    assert draft["sale_number"] == "SALE-000001"
    assert draft["status"] == "DRAFT"
    assert draft["subtotal"] == "91.25"
    assert [item["product_name_snapshot"] for item in draft["items"]] == [
        "Mango",
        "Water",
    ]

    updated = await client.patch(
        f"/api/v1/sales/{draft['id']}",
        headers=headers,
        json={
            "customer_id": second_customer["id"],
            "items": [_line(mango, "4", "15")],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sale"]["customer_name"] == "Second Shop"
    assert updated.json()["sale"]["subtotal"] == "60.00"
    assert len(updated.json()["sale"]["items"]) == 1

    by_id = await client.get(f"/api/v1/sales/{draft['id']}", headers=headers)
    by_number = await client.get(
        f"/api/v1/sales/number/{draft['sale_number']}", headers=headers
    )
    assert by_id.status_code == by_number.status_code == 200
    assert by_number.json()["sale_number"] == "SALE-000001"

    delete_attempt = await client.delete(f"/api/v1/sales/{draft['id']}", headers=headers)
    assert delete_attempt.status_code == 405
    assert (await client.get(f"/api/v1/sales/{draft['id']}", headers=headers)).status_code == 200


@pytest.mark.parametrize(
    ("items", "field", "message"),
    [
        ([], "items", "Add at least one product to this sale."),
        (
            [{"product_id": str(uuid4()), "quantity": "0", "unit_price": "1"}],
            "items.0.quantity",
            "Quantity must be greater than zero.",
        ),
        (
            [{"product_id": str(uuid4()), "quantity": "-1", "unit_price": "1"}],
            "items.0.quantity",
            "Quantity must be greater than zero.",
        ),
        (
            [{"product_id": str(uuid4()), "quantity": "1", "unit_price": "0"}],
            "items.0.unit_price",
            "Unit price must be greater than zero.",
        ),
        (
            [{"product_id": str(uuid4()), "quantity": "1", "unit_price": "-1"}],
            "items.0.unit_price",
            "Unit price must be greater than zero.",
        ),
    ],
)
async def test_sale_numeric_validation_is_actionable(
    client: AsyncClient,
    items: list[dict[str, str]],
    field: str,
    message: str,
) -> None:
    _, headers = await _signup(client, f"validation-{field}")
    customer = await _customer(client, headers, f"Validation {field}")
    response = await _sale(client, headers, customer, items)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    actual = response.json()["error"]["field_errors"]
    assert actual[field] == message


async def test_sale_item_shape_validation_is_actionable(client: AsyncClient) -> None:
    _, headers = await _signup(client, "item-shape")
    customer = await _customer(client, headers, "Shape Customer")
    response = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": "shape-key"},
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": "not-a-product-id", "quantity": "1"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["field_errors"] == {
        "items.0.product_id": "Select a valid product.",
        "items.0.unit_price": "Unit price is required.",
    }


async def test_duplicate_archived_and_unknown_records_are_rejected(client: AsyncClient) -> None:
    _, headers = await _signup(client, "records")
    customer = await _customer(client, headers, "Archived Customer")
    product = await _product(client, headers, "Archived Product")
    duplicate = await _sale(
        client, headers, customer, [_line(product), _line(product, "2")]
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "DUPLICATE_SALE_PRODUCT"

    await client.post(f"/api/v1/customers/{customer['id']}/archive", headers=headers)
    archived_customer = await _sale(client, headers, customer, [_line(product)])
    assert archived_customer.status_code == 422
    assert archived_customer.json()["error"]["code"] == "CUSTOMER_ARCHIVED"
    await client.post(f"/api/v1/customers/{customer['id']}/restore", headers=headers)

    await client.post(f"/api/v1/products/{product['id']}/archive", headers=headers)
    archived_product = await _sale(client, headers, customer, [_line(product)])
    assert archived_product.status_code == 422
    assert archived_product.json()["error"]["code"] == "PRODUCT_ARCHIVED"
    await client.post(f"/api/v1/products/{product['id']}/restore", headers=headers)

    unknown_customer = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"customer_id": str(uuid4()), "items": [_line(product)]},
    )
    assert unknown_customer.status_code == 404
    assert unknown_customer.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"
    unknown_product = await _sale(
        client,
        headers,
        customer,
        [{"product_id": str(uuid4()), "quantity": "1", "unit_price": "1"}],
    )
    assert unknown_product.status_code == 404
    assert unknown_product.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_post_deducts_inventory_and_freezes_snapshots(client: AsyncClient) -> None:
    _, headers = await _signup(client, "post")
    customer = await _customer(client, headers, "Post Customer")
    product = await _product(client, headers, "Original Mango", price="25", unit="kg")
    await _stock(client, headers, product["id"], "10")
    draft = (await _sale(client, headers, customer, [_line(product, "3")])).json()["sale"]

    posted = await client.post(
        f"/api/v1/sales/{draft['id']}/post",
        headers={**headers, "Idempotency-Key": "post-once"},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["sale"]["status"] == "POSTED"
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "7.000"
    history = await client.get(
        "/api/v1/inventory/history",
        headers=headers,
        params={"product_id": product["id"]},
    )
    assert history.json()["items"][0]["movement_type"] == "SALE"
    assert history.json()["items"][0]["quantity"] == "-3.000"

    second_draft = (
        await _sale(client, headers, customer, [_line(product, "2")], key="second-snapshot")
    ).json()["sale"]
    second_posted = await client.post(
        f"/api/v1/sales/{second_draft['id']}/post",
        headers={**headers, "Idempotency-Key": "second-snapshot-post"},
    )
    assert second_posted.status_code == 200, second_posted.text

    blocked_product_update = await client.patch(
        f"/api/v1/products/{product['id']}",
        headers=headers,
        json={"name": "Renamed Mango", "selling_price": "99", "unit": "piece"},
    )
    assert blocked_product_update.status_code == 409
    assert blocked_product_update.json()["error"]["code"] == "PRODUCT_UNIT_LOCKED"
    unchanged_product = await client.get(
        f"/api/v1/products/{product['id']}", headers=headers
    )
    assert unchanged_product.json()["name"] == "Original Mango"
    assert unchanged_product.json()["selling_price"] == "25.00"
    assert unchanged_product.json()["unit"] == "kg"

    allowed_product_update = await client.patch(
        f"/api/v1/products/{product['id']}",
        headers=headers,
        json={"name": "Renamed Mango", "selling_price": "99"},
    )
    assert allowed_product_update.status_code == 200, allowed_product_update.text
    assert allowed_product_update.json()["product"]["name"] == "Renamed Mango"
    assert allowed_product_update.json()["product"]["selling_price"] == "99.00"
    assert allowed_product_update.json()["product"]["unit"] == "kg"

    for sale_id, expected_quantity, expected_total in (
        (draft["id"], "3.000", "75.00"),
        (second_draft["id"], "2.000", "50.00"),
    ):
        historical = await client.get(f"/api/v1/sales/{sale_id}", headers=headers)
        assert historical.status_code == 200
        item = historical.json()["items"][0]
        assert item["product_name_snapshot"] == "Original Mango"
        assert item["unit_snapshot"] == "kg"
        assert item["unit_price"] == "25.00"
        assert item["quantity"] == expected_quantity
        assert item["line_total"] == expected_total

    blocked_edit = await client.patch(
        f"/api/v1/sales/{draft['id']}",
        headers=headers,
        json={"items": [_line(product, "1")]},
    )
    assert blocked_edit.status_code == 409
    assert blocked_edit.json()["error"]["code"] == "SALE_NOT_EDITABLE"


async def test_void_reverses_inventory_even_after_product_archive(client: AsyncClient) -> None:
    _, headers = await _signup(client, "void")
    customer = await _customer(client, headers, "Void Customer")
    product = await _product(client, headers, "Void Product")
    await _stock(client, headers, product["id"], "5")
    sale = (await _sale(client, headers, customer, [_line(product, "2")])).json()["sale"]
    await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": "void-post"},
    )
    await client.post(f"/api/v1/products/{product['id']}/archive", headers=headers)

    voided = await client.post(
        f"/api/v1/sales/{sale['id']}/void",
        headers={**headers, "Idempotency-Key": "void-once"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["sale"]["status"] == "VOID"
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "5.000"
    history = await client.get(
        "/api/v1/inventory/history",
        headers=headers,
        params={"product_id": product["id"]},
    )
    assert [item["movement_type"] for item in history.json()["items"][:2]] == [
        "SALE_VOID",
        "SALE",
    ]


async def test_void_rejects_a_missing_inventory_projection(
    client: AsyncClient, test_settings: Settings
) -> None:
    _, headers = await _signup(client, "void-projection")
    customer = await _customer(client, headers, "Projection Customer")
    product = await _product(client, headers, "Projection Product")
    await _stock(client, headers, product["id"], "5")
    sale = (await _sale(client, headers, customer, [_line(product, "2")])).json()["sale"]
    posted = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": "projection-post"},
    )
    assert posted.status_code == 200
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    async with engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text("DELETE FROM stock_balances WHERE product_id = :product_id"),
            {"product_id": product["id"]},
        )
    await engine.dispose()

    response = await client.post(
        f"/api/v1/sales/{sale['id']}/void",
        headers={**headers, "Idempotency-Key": "projection-void"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SALE_INVENTORY_PROJECTION_MISSING"
    unchanged = await client.get(f"/api/v1/sales/{sale['id']}", headers=headers)
    assert unchanged.json()["status"] == "POSTED"


async def test_insufficient_stock_rolls_back_every_sale_item(client: AsyncClient) -> None:
    _, headers = await _signup(client, "rollback")
    customer = await _customer(client, headers, "Rollback Customer")
    first = await _product(client, headers, "Enough Stock")
    second = await _product(client, headers, "Not Enough Stock")
    await _stock(client, headers, first["id"], "10")
    await _stock(client, headers, second["id"], "1")
    sale = (
        await _sale(client, headers, customer, [_line(first, "3"), _line(second, "2")])
    ).json()["sale"]

    response = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": "rollback-post"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert "Only 1 piece available for Not Enough Stock" in response.json()["error"]["message"]
    saved_sale = await client.get(f"/api/v1/sales/{sale['id']}", headers=headers)
    assert saved_sale.json()["status"] == "DRAFT"
    for product, expected in ((first, "10.000"), (second, "1.000")):
        current = await client.get(
            f"/api/v1/inventory/stock/{product['id']}", headers=headers
        )
        assert current.json()["available_quantity"] == expected


async def test_default_warehouse_cannot_be_archived_and_sales_continue(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    session, headers = await _signup(client, "archived-default-warehouse")
    customer = await _customer(client, headers, "Warehouse Edge Customer")
    product = await _product(client, headers, "Warehouse Edge Product")
    await _stock(client, headers, product["id"], "3")
    sale = (await _sale(client, headers, customer, [_line(product, "1")])).json()["sale"]
    warehouse = await client.get("/api/v1/inventory/warehouses/default", headers=headers)
    assert warehouse.status_code == 200, warehouse.text

    admin_url = test_settings.database_admin_url
    assert admin_url is not None
    engine = create_async_engine(admin_url)
    with pytest.raises(IntegrityError):
        try:
            async with engine.begin() as connection:
                await set_internal_maintenance_context(connection)
                await connection.execute(
                    text(
                        """
                        UPDATE warehouses
                        SET archived = true
                        WHERE tenant_id = :tenant_id
                          AND id = :warehouse_id
                        """
                    ),
                    {
                        "tenant_id": session["user"]["business"]["id"],
                        "warehouse_id": warehouse.json()["id"],
                    },
                )
        finally:
            await engine.dispose()

    posted = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": "default-warehouse-still-active"},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["sale"]["status"] == "POSTED"
    balance = await client.get(
        f"/api/v1/inventory/stock/{product['id']}",
        headers=headers,
    )
    assert balance.status_code == 200, balance.text
    assert balance.json()["available_quantity"] == "2.000"


async def test_create_post_and_void_are_idempotent(client: AsyncClient) -> None:
    _, headers = await _signup(client, "idempotency")
    customer = await _customer(client, headers, "Idempotent Customer")
    product = await _product(client, headers, "Idempotent Product")
    await _stock(client, headers, product["id"], "10")
    payload = [_line(product, "2")]
    creates = await asyncio.gather(
        _sale(client, headers, customer, payload, key="same-create"),
        _sale(client, headers, customer, payload, key="same-create"),
    )
    assert [response.status_code for response in creates] == [201, 201]
    assert creates[0].json()["sale"]["id"] == creates[1].json()["sale"]["id"]
    sale = creates[0].json()["sale"]

    posts = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/sales/{sale['id']}/post",
                headers={**headers, "Idempotency-Key": "same-post"},
            )
            for _ in range(2)
        ]
    )
    assert all(response.status_code == 200 for response in posts)
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "8.000"
    other_sale = (await _sale(client, headers, customer, [_line(product, "1")])).json()["sale"]
    reused_post_key = await client.post(
        f"/api/v1/sales/{other_sale['id']}/post",
        headers={**headers, "Idempotency-Key": "same-post"},
    )
    assert reused_post_key.status_code == 409
    assert reused_post_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "8.000"

    voids = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/sales/{sale['id']}/void",
                headers={**headers, "Idempotency-Key": "same-void"},
            )
            for _ in range(2)
        ]
    )
    assert all(response.status_code == 200 for response in voids)
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "10.000"


async def test_concurrent_sales_cannot_oversell(client: AsyncClient) -> None:
    _, headers = await _signup(client, "concurrent")
    customer = await _customer(client, headers, "Concurrent Customer")
    product = await _product(client, headers, "Scarce Product")
    await _stock(client, headers, product["id"], "5")
    first = (await _sale(client, headers, customer, [_line(product, "4")])).json()["sale"]
    second = (await _sale(client, headers, customer, [_line(product, "4")])).json()["sale"]
    responses = await asyncio.gather(
        client.post(
            f"/api/v1/sales/{first['id']}/post",
            headers={**headers, "Idempotency-Key": "concurrent-first"},
        ),
        client.post(
            f"/api/v1/sales/{second['id']}/post",
            headers={**headers, "Idempotency-Key": "concurrent-second"},
        ),
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "1.000"


async def test_sale_numbers_are_concurrency_safe(client: AsyncClient) -> None:
    _, headers = await _signup(client, "numbers")
    customer = await _customer(client, headers, "Number Customer")
    product = await _product(client, headers, "Number Product")
    responses = await asyncio.gather(
        *[
            _sale(client, headers, customer, [_line(product)], key=f"number-{number}")
            for number in range(5)
        ]
    )
    assert all(response.status_code == 201 for response in responses)
    assert {response.json()["sale"]["sale_number"] for response in responses} == {
        f"SALE-{number:06d}" for number in range(1, 6)
    }


async def test_sales_search_filters_sort_and_cursor_pagination(client: AsyncClient) -> None:
    _, headers = await _signup(client, "search")
    alpha = await _customer(client, headers, "Alpha Stores")
    beta = await _customer(client, headers, "Beta Stores")
    product = await _product(client, headers, "Search Product")
    sales = []
    for number in range(4):
        customer = alpha if number % 2 == 0 else beta
        sales.append((await _sale(client, headers, customer, [_line(product)])).json()["sale"])
    first = await client.get("/api/v1/sales", headers=headers, params={"limit": 2})
    second = await client.get(
        "/api/v1/sales",
        headers=headers,
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert first.json()["has_more"] is True
    assert {item["id"] for item in first.json()["items"]}.isdisjoint(
        {item["id"] for item in second.json()["items"]}
    )

    by_number = await client.get(
        "/api/v1/sales/search", headers=headers, params={"q": sales[0]["sale_number"]}
    )
    assert by_number.json()["items"][0]["id"] == sales[0]["id"]
    by_customer = await client.get(
        "/api/v1/sales/search", headers=headers, params={"q": "beta"}
    )
    assert all(item["customer_name"] == "Beta Stores" for item in by_customer.json()["items"])
    sale_date = datetime.fromisoformat(sales[0]["created_at"]).astimezone(
        ZoneInfo("Asia/Kolkata")
    ).date()
    by_date = await client.get(
        "/api/v1/sales/search", headers=headers, params={"date": sale_date.isoformat()}
    )
    assert len(by_date.json()["items"]) == 4
    drafts = await client.get(
        "/api/v1/sales", headers=headers, params={"status": "draft"}
    )
    assert len(drafts.json()["items"]) == 4
    oldest = await client.get(
        "/api/v1/sales", headers=headers, params={"sort": "oldest"}
    )
    assert oldest.json()["items"][0]["id"] == sales[0]["id"]


async def test_exact_decimal_and_zero_quantity_rules(client: AsyncClient) -> None:
    _, headers = await _signup(client, "quantity-boundaries")
    customer = await _customer(client, headers, "Boundary Customer")
    product = await _product(
        client,
        headers,
        "Decimal Stock",
        price="4.25",
        unit="kg",
    )
    await _stock(client, headers, product["id"], "3.750")

    decimal_sale = await _sale(client, headers, customer, [_line(product, "1.250")])
    assert decimal_sale.status_code == 201
    decimal_post = await client.post(
        f"/api/v1/sales/{decimal_sale.json()['sale']['id']}/post",
        headers={**headers, "Idempotency-Key": "decimal-post"},
    )
    assert decimal_post.status_code == 200
    assert decimal_post.json()["sale"]["subtotal"] == "5.31"

    exact_sale = await _sale(client, headers, customer, [_line(product, "2.500")])
    exact_post = await client.post(
        f"/api/v1/sales/{exact_sale.json()['sale']['id']}/post",
        headers={**headers, "Idempotency-Key": "exact-post"},
    )
    assert exact_post.status_code == 200
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "0.000"

    zero = await _sale(client, headers, customer, [_line(product, "0")])
    assert zero.status_code == 422
    assert zero.json()["error"]["field_errors"]["items.0.quantity"] == (
        "Quantity must be greater than zero."
    )


async def test_stale_draft_edit_is_rejected(client: AsyncClient) -> None:
    _, headers = await _signup(client, "edit-conflict")
    customer = await _customer(client, headers, "Concurrent Editor")
    product = await _product(client, headers, "Concurrent Product")
    draft = (await _sale(client, headers, customer, [_line(product)])).json()["sale"]
    stale_timestamp = draft["updated_at"]

    first = await client.patch(
        f"/api/v1/sales/{draft['id']}",
        headers=headers,
        json={
            "items": [_line(product, "2")],
            "expected_updated_at": stale_timestamp,
        },
    )
    second = await client.patch(
        f"/api/v1/sales/{draft['id']}",
        headers=headers,
        json={
            "items": [_line(product, "3")],
            "expected_updated_at": stale_timestamp,
        },
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SALE_EDIT_CONFLICT"
    latest = await client.get(f"/api/v1/sales/{draft['id']}", headers=headers)
    assert latest.json()["items"][0]["quantity"] == "2.000"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/sales", None),
        ("GET", "/api/v1/sales/search?q=sale", None),
        ("GET", f"/api/v1/sales/{uuid4()}", None),
        ("GET", "/api/v1/sales/number/SALE-000001", None),
        ("POST", "/api/v1/sales", {}),
        ("PATCH", f"/api/v1/sales/{uuid4()}", {}),
        ("POST", f"/api/v1/sales/{uuid4()}/post", None),
        ("POST", f"/api/v1/sales/{uuid4()}/void", None),
    ],
)
async def test_every_sales_endpoint_requires_authentication(
    client: AsyncClient,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    response = await client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
