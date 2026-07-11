import asyncio
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.modules.identity.security import decode_access_token
from distributoros.modules.inventory.reconciliation import InventoryReconciliationService


async def _signup(
    client: AsyncClient, *, suffix: str = "inventory"
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Inventory {suffix}",
            "email": f"{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    session: dict[str, Any] = response.json()
    return session, {"Authorization": f"Bearer {session['access_token']}"}


async def _product(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    threshold: str = "2",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "selling_price": "10",
            "unit": "kg",
            "low_stock_threshold": threshold,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]


async def _post(
    client: AsyncClient,
    headers: dict[str, str],
    path: str,
    product_id: str,
    quantity: str,
    *,
    key: str | None = None,
    **fields: str,
) -> Any:
    response = await client.post(
        f"/api/v1/inventory/{path}",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json={"product_id": product_id, "quantity": quantity, **fields},
    )
    assert response.status_code == 201, response.text
    return response


async def test_default_warehouse_and_all_movement_types(client: AsyncClient) -> None:
    _, headers = await _signup(client)
    warehouse = await client.get("/api/v1/inventory/warehouses/default", headers=headers)
    assert warehouse.status_code == 200
    assert warehouse.json()["name"] == "Main Warehouse"
    assert warehouse.json()["is_default"] is True
    product = await _product(client, headers, "Loose Rice")

    operations = [
        ("opening-stock", "10.500", {}, "OPENING_STOCK", "10.500"),
        ("stock-receipts", "2.250", {"remarks": "Morning delivery"}, "STOCK_RECEIPT", "2.250"),
        ("adjustments", "-1", {"reason": "Stock count correction"}, "STOCK_ADJUSTMENT", "-1.000"),
        ("customer-returns", "1", {}, "CUSTOMER_RETURN", "1.000"),
        ("damage", "0.500", {}, "DAMAGED", "-0.500"),
        ("spoilage", "0.250", {}, "SPOILAGE", "-0.250"),
    ]
    for path, quantity, fields, movement_type, stored_quantity in operations:
        response = await _post(
            client, headers, path, product["id"], quantity, **fields
        )
        assert response.json()["movement"]["movement_type"] == movement_type
        assert response.json()["movement"]["quantity"] == stored_quantity

    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.status_code == 200
    assert current.json()["available_quantity"] == "12.000"
    assert current.json()["unit"] == "kg"
    assert current.json()["low_stock_status"] == "NORMAL"

    history = await client.get("/api/v1/inventory/history", headers=headers)
    assert [item["movement_type"] for item in history.json()["items"]] == [
        "SPOILAGE",
        "DAMAGED",
        "CUSTOMER_RETURN",
        "STOCK_ADJUSTMENT",
        "STOCK_RECEIPT",
        "OPENING_STOCK",
    ]
    assert history.json()["items"][0]["created_by_email"] == "inventory@example.com"


async def test_stock_status_search_and_keyset_pagination(client: AsyncClient) -> None:
    _, headers = await _signup(client, suffix="stock-list")
    out = await _product(client, headers, "Alpha Apples", threshold="2")
    low = await _product(client, headers, "Bravo Bananas", threshold="2")
    normal = await _product(client, headers, "Charlie Cherries", threshold="2")
    await _post(client, headers, "opening-stock", low["id"], "2")
    await _post(client, headers, "opening-stock", normal["id"], "3")

    first = await client.get(
        "/api/v1/inventory/stock", headers=headers, params={"limit": 2}
    )
    assert [item["product_name"] for item in first.json()["items"]] == [
        "Alpha Apples",
        "Bravo Bananas",
    ]
    assert [item["low_stock_status"] for item in first.json()["items"]] == [
        "OUT_OF_STOCK",
        "LOW_STOCK",
    ]
    assert first.json()["has_more"] is True
    second = await client.get(
        "/api/v1/inventory/stock",
        headers=headers,
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert second.json()["items"][0]["product_id"] == normal["id"]
    assert second.json()["items"][0]["low_stock_status"] == "NORMAL"

    search = await client.get(
        "/api/v1/inventory/stock", headers=headers, params={"search": "bravo"}
    )
    assert [item["product_id"] for item in search.json()["items"]] == [low["id"]]
    history_search = await client.get(
        "/api/v1/inventory/history", headers=headers, params={"search": "charlie"}
    )
    assert history_search.json()["items"][0]["product_id"] == normal["id"]
    assert out["id"] not in [item["product_id"] for item in history_search.json()["items"]]


@pytest.mark.parametrize(
    ("path", "payload", "field", "message"),
    [
        ("opening-stock", {"quantity": "-1"}, "quantity", "Quantity must be greater than zero."),
        ("stock-receipts", {"quantity": "0"}, "quantity", "Quantity must not be zero."),
        (
            "customer-returns",
            {"quantity": "1.0001"},
            "quantity",
            "Quantity can have at most 3 decimal places.",
        ),
        (
            "adjustments",
            {"quantity": "1", "reason": ""},
            "reason",
            "Reason is required for a stock adjustment.",
        ),
    ],
)
async def test_inventory_validation_is_actionable(
    client: AsyncClient,
    path: str,
    payload: dict[str, str],
    field: str,
    message: str,
) -> None:
    _, headers = await _signup(client, suffix=f"validate-{path}")
    product = await _product(client, headers, f"Validate {path}")
    response = await client.post(
        f"/api/v1/inventory/{path}",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product["id"], **payload},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["field_errors"][field] == message
    assert "traceback" not in response.text.lower()
    assert "sql" not in response.text.lower()


async def test_archived_product_and_invalid_product_are_rejected(client: AsyncClient) -> None:
    _, headers = await _signup(client, suffix="archived")
    product = await _product(client, headers, "Archived Flour")
    await client.post(f"/api/v1/products/{product['id']}/archive", headers=headers)
    archived = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product["id"], "quantity": "1"},
    )
    assert archived.status_code == 422
    assert archived.json()["error"]["code"] == "PRODUCT_ARCHIVED"
    assert archived.json()["error"]["field_errors"]["product_id"] == (
        "Selected product has been archived."
    )

    missing = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": str(uuid4()), "quantity": "1"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_opening_stock_is_once_and_product_unit_locks(client: AsyncClient) -> None:
    _, headers = await _signup(client, suffix="opening")
    product = await _product(client, headers, "Unit Locked")
    await _post(client, headers, "opening-stock", product["id"], "3")
    duplicate = await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product["id"], "quantity": "2"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "OPENING_STOCK_ALREADY_RECORDED"

    unit_change = await client.patch(
        f"/api/v1/products/{product['id']}", headers=headers, json={"unit": "piece"}
    )
    assert unit_change.status_code == 409
    assert unit_change.json()["error"]["code"] == "PRODUCT_UNIT_LOCKED"
    assert unit_change.json()["error"]["field_errors"]["unit"].startswith(
        "Unit cannot be changed"
    )


async def test_insufficient_stock_rolls_back_movement(client: AsyncClient) -> None:
    _, headers = await _signup(client, suffix="rollback")
    product = await _product(client, headers, "Rollback Product")
    await _post(client, headers, "opening-stock", product["id"], "2")
    response = await client.post(
        "/api/v1/inventory/damage",
        headers={**headers, "Idempotency-Key": "failed-damage"},
        json={"product_id": product["id"], "quantity": "3"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "2.000"
    history = await client.get(
        "/api/v1/inventory/history",
        headers=headers,
        params={"product_id": product["id"]},
    )
    assert [item["movement_type"] for item in history.json()["items"]] == [
        "OPENING_STOCK"
    ]


async def test_idempotency_and_concurrent_updates(client: AsyncClient) -> None:
    _, headers = await _signup(client, suffix="concurrent")
    product = await _product(client, headers, "Concurrent Stock")
    await _post(client, headers, "opening-stock", product["id"], "1")
    duplicate_key = "same-receipt"
    duplicates = await asyncio.gather(
        *[
            client.post(
                "/api/v1/inventory/stock-receipts",
                headers={**headers, "Idempotency-Key": duplicate_key},
                json={"product_id": product["id"], "quantity": "2"},
            )
            for _ in range(2)
        ]
    )
    assert [response.status_code for response in duplicates] == [201, 201]
    assert duplicates[0].json()["movement"]["id"] == duplicates[1].json()["movement"]["id"]

    concurrent = await asyncio.gather(
        *[
            client.post(
                "/api/v1/inventory/stock-receipts",
                headers={**headers, "Idempotency-Key": f"receipt-{number}"},
                json={"product_id": product["id"], "quantity": "1"},
            )
            for number in range(10)
        ]
    )
    assert all(response.status_code == 201 for response in concurrent)
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "13.000"
    history = await client.get(
        "/api/v1/inventory/history",
        headers=headers,
        params={"product_id": product["id"], "limit": 100},
    )
    assert len(history.json()["items"]) == 12
    first_page = await client.get(
        "/api/v1/inventory/history",
        headers=headers,
        params={"product_id": product["id"], "limit": 5},
    )
    second_page = await client.get(
        "/api/v1/inventory/history",
        headers=headers,
        params={
            "product_id": product["id"],
            "limit": 5,
            "cursor": first_page.json()["next_cursor"],
        },
    )
    first_ids = {item["id"] for item in first_page.json()["items"]}
    second_ids = {item["id"] for item in second_page.json()["items"]}
    assert len(first_ids) == len(second_ids) == 5
    assert first_ids.isdisjoint(second_ids)

    reused = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers, "Idempotency-Key": duplicate_key},
        json={"product_id": product["id"], "quantity": "9"},
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_concurrent_decrements_cannot_create_negative_stock(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, suffix="concurrent-decrement")
    product = await _product(client, headers, "Concurrent Decrement")
    await _post(client, headers, "opening-stock", product["id"], "10")
    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/inventory/damage",
                headers={**headers, "Idempotency-Key": f"damage-{number}"},
                json={"product_id": product["id"], "quantity": "6"},
            )
            for number in range(2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert next(
        response.json()["error"]["code"]
        for response in responses
        if response.status_code == 409
    ) == "INSUFFICIENT_STOCK"
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "4.000"


async def test_projection_can_be_rebuilt_from_movements(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_data, headers = await _signup(client, suffix="rebuild")
    product = await _product(client, headers, "Rebuild Stock")
    await _post(client, headers, "opening-stock", product["id"], "5")
    await _post(client, headers, "damage", product["id"], "1")
    claims = decode_access_token(test_settings, session_data["access_token"])
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    async with engine.begin() as connection:
        balance = await connection.execute(
            text(
                "UPDATE stock_balances SET available_quantity = 999 "
                "WHERE tenant_id = :tenant_id"
            ),
            {"tenant_id": claims.business_id},
        )
        assert balance.rowcount == 1
    result = await InventoryReconciliationService(engine).rebuild()
    await engine.dispose()
    assert result.before.is_consistent is False
    assert result.after.is_consistent is True

    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "4.000"


async def test_archived_warehouse_is_rejected(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_data, headers = await _signup(client, suffix="archived-warehouse")
    product = await _product(client, headers, "Warehouse Product")
    claims = decode_access_token(test_settings, session_data["access_token"])
    warehouse_id = uuid4()
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO warehouses "
                "(id, tenant_id, name, is_default, archived, created_at) "
                "VALUES (:id, :tenant_id, 'Archived Location', false, true, now())"
            ),
            {"id": warehouse_id, "tenant_id": claims.business_id},
        )
    await engine.dispose()
    response = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "product_id": product["id"],
            "warehouse_id": str(warehouse_id),
            "quantity": "1",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WAREHOUSE_ARCHIVED"
    assert response.json()["error"]["field_errors"]["warehouse_id"] == (
        "This warehouse is archived."
    )


async def test_stock_movements_cannot_be_updated_or_deleted(
    client: AsyncClient, test_settings: Settings
) -> None:
    _, headers = await _signup(client, suffix="immutable")
    product = await _product(client, headers, "Immutable Stock")
    posted = await _post(client, headers, "opening-stock", product["id"], "5")
    movement_id = posted.json()["movement"]["id"]
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    with pytest.raises(DBAPIError):
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE stock_movements SET quantity = 6 WHERE id = :id"),
                {"id": movement_id},
            )
    with pytest.raises(DBAPIError):
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM stock_movements WHERE id = :id"),
                {"id": movement_id},
            )
    async with engine.begin() as connection:
        quantity = await connection.scalar(
            text("SELECT quantity FROM stock_movements WHERE id = :id"),
            {"id": movement_id},
        )
    await engine.dispose()
    assert str(quantity) == "5.000"


async def test_missing_idempotency_and_extra_movement_type_are_rejected(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, suffix="submission")
    product = await _product(client, headers, "Submission Product")
    missing_key = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers=headers,
        json={"product_id": product["id"], "quantity": "1"},
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    unknown_type = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "product_id": product["id"],
            "quantity": "1",
            "movement_type": "SALE",
        },
    )
    assert unknown_type.status_code == 422
    assert unknown_type.json()["error"]["field_errors"]["movement_type"] == (
        "Movement type is not accepted. Remove it and try again."
    )


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/inventory/warehouses/default", None),
        ("GET", "/api/v1/inventory/stock", None),
        ("GET", f"/api/v1/inventory/stock/{uuid4()}", None),
        ("GET", "/api/v1/inventory/history", None),
        ("POST", "/api/v1/inventory/opening-stock", {}),
        ("POST", "/api/v1/inventory/stock-receipts", {}),
        ("POST", "/api/v1/inventory/adjustments", {}),
        ("POST", "/api/v1/inventory/customer-returns", {}),
        ("POST", "/api/v1/inventory/damage", {}),
        ("POST", "/api/v1/inventory/spoilage", {}),
    ],
)
async def test_every_inventory_endpoint_requires_authentication(
    client: AsyncClient, method: str, path: str, payload: dict[str, str] | None
) -> None:
    response = await client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
