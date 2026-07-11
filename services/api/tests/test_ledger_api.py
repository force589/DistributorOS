import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings


async def _signup(client: AsyncClient, suffix: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Ledger {suffix}",
            "email": f"ledger-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _customer(client: AsyncClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    response = await client.post("/api/v1/customers", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["customer"]


async def _product(
    client: AsyncClient, headers: dict[str, str], name: str, price: str = "10"
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "selling_price": price,
            "unit": "piece",
            "low_stock_threshold": "0",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]


async def _stock(
    client: AsyncClient, headers: dict[str, str], product_id: str, quantity: str = "100"
) -> None:
    response = await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product_id, "quantity": quantity},
    )
    assert response.status_code == 201, response.text


async def _draft(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    product: dict[str, Any],
    quantity: str,
    *,
    key: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": quantity,
                    "unit_price": product["selling_price"],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["sale"]


async def _post(
    client: AsyncClient, headers: dict[str, str], sale_id: str, key: str
) -> Any:
    return await client.post(
        f"/api/v1/sales/{sale_id}/post",
        headers={**headers, "Idempotency-Key": key},
    )


async def test_sale_posting_and_void_create_immutable_financial_entries(
    client: AsyncClient,
) -> None:
    headers = await _signup(client, "posting")
    customer = await _customer(client, headers, "Financial Customer")
    product = await _product(client, headers, "Ledger Product", "20")
    await _stock(client, headers, product["id"])
    first = await _draft(
        client, headers, customer["id"], product, "1", key="ledger-first"
    )
    second = await _draft(
        client, headers, customer["id"], product, "2", key="ledger-second"
    )
    assert (await _post(client, headers, first["id"], "post-first")).status_code == 200
    assert (await _post(client, headers, second["id"], "post-second")).status_code == 200

    summary = await client.get(
        f"/api/v1/customers/{customer['id']}/financial-summary", headers=headers
    )
    assert summary.status_code == 200
    assert summary.json()["outstanding_balance"] == "60.00"
    assert summary.json()["total_sales"] == "60.00"
    assert summary.json()["last_sale_date"] is not None

    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers
    )
    assert ledger.status_code == 200, ledger.text
    assert [entry["reference"] for entry in ledger.json()["items"]] == [
        second["sale_number"],
        first["sale_number"],
    ]
    assert [entry["running_balance"] for entry in ledger.json()["items"]] == [
        "60.00",
        "20.00",
    ]
    assert ledger.json()["items"][0]["debit"] == "40.00"
    assert ledger.json()["items"][0]["credit"] == "0.00"

    voided = await client.post(
        f"/api/v1/sales/{second['id']}/void",
        headers={**headers, "Idempotency-Key": "void-second"},
    )
    assert voided.status_code == 200, voided.text
    summary = await client.get(
        f"/api/v1/customers/{customer['id']}/financial-summary", headers=headers
    )
    assert summary.json()["outstanding_balance"] == "20.00"
    assert summary.json()["total_sales"] == "20.00"
    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers
    )
    entries = ledger.json()["items"]
    assert entries[0]["entry_type"] == "REVERSAL"
    assert entries[0]["credit"] == "40.00"
    assert entries[0]["running_balance"] == "20.00"
    assert [entry["entry_type"] for entry in entries].count("SALE") == 2
    assert [entry["entry_type"] for entry in entries].count("REVERSAL") == 1


async def test_ledger_search_date_type_and_cursor_pagination(client: AsyncClient) -> None:
    headers = await _signup(client, "search")
    customer = await _customer(client, headers, "Search Ledger")
    product = await _product(client, headers, "Search Product", "5")
    await _stock(client, headers, product["id"])
    sales = []
    for index in range(3):
        sale = await _draft(
            client,
            headers,
            customer["id"],
            product,
            "1",
            key=f"search-draft-{index}",
        )
        assert (await _post(client, headers, sale["id"], f"search-post-{index}")).status_code == 200
        sales.append(sale)

    first = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger",
        headers=headers,
        params={"limit": 2},
    )
    second = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger",
        headers=headers,
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert first.json()["has_more"] is True
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 1
    assert {entry["id"] for entry in first.json()["items"]}.isdisjoint(
        {entry["id"] for entry in second.json()["items"]}
    )

    by_reference = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger/search",
        headers=headers,
        params={"q": sales[0]["sale_number"]},
    )
    assert [entry["reference"] for entry in by_reference.json()["items"]] == [
        sales[0]["sale_number"]
    ]
    sale_date = datetime.fromisoformat(
        by_reference.json()["items"][0]["created_at"]
    ).astimezone(ZoneInfo("Asia/Kolkata")).date()
    by_date = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger/search",
        headers=headers,
        params={"date": sale_date.isoformat()},
    )
    assert len(by_date.json()["items"]) == 3
    by_type = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger/search",
        headers=headers,
        params={"entry_type": "sale"},
    )
    assert all(entry["entry_type"] == "SALE" for entry in by_type.json()["items"])


async def test_duplicate_and_concurrent_posting_do_not_duplicate_receivables(
    client: AsyncClient,
) -> None:
    headers = await _signup(client, "concurrent")
    customer = await _customer(client, headers, "Concurrent Ledger")
    first_product = await _product(client, headers, "Concurrent First", "7")
    second_product = await _product(client, headers, "Concurrent Second", "11")
    await _stock(client, headers, first_product["id"])
    await _stock(client, headers, second_product["id"])
    first = await _draft(
        client, headers, customer["id"], first_product, "2", key="concurrent-first"
    )
    second = await _draft(
        client, headers, customer["id"], second_product, "3", key="concurrent-second"
    )
    responses = await asyncio.gather(
        _post(client, headers, first["id"], "post-concurrent-first"),
        _post(client, headers, second["id"], "post-concurrent-second"),
    )
    assert all(response.status_code == 200 for response in responses)
    duplicate = await _post(client, headers, first["id"], "post-concurrent-first")
    assert duplicate.status_code == 200
    summary = await client.get(
        f"/api/v1/customers/{customer['id']}/financial-summary", headers=headers
    )
    assert summary.json()["outstanding_balance"] == "47.00"
    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers
    )
    assert len(ledger.json()["items"]) == 2


async def test_ledger_failure_rolls_back_inventory_and_sale(
    client: AsyncClient, test_settings: Settings
) -> None:
    headers = await _signup(client, "rollback")
    customer = await _customer(client, headers, "Rollback Ledger")
    product = await _product(client, headers, "Rollback Product", "10")
    await _stock(client, headers, product["id"], "5")
    sale = await _draft(
        client, headers, customer["id"], product, "2", key="rollback-draft"
    )
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE FUNCTION test_reject_ledger_insert() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                    RAISE EXCEPTION 'forced ledger failure';
                END; $$
                """
            )
        )
        await connection.execute(
            text(
                """
                CREATE TRIGGER test_reject_ledger_insert
                BEFORE INSERT ON customer_ledger_entries
                FOR EACH ROW EXECUTE FUNCTION test_reject_ledger_insert()
                """
            )
        )
    try:
        response = await _post(client, headers, sale["id"], "rollback-post")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "forced ledger failure" not in response.text
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "DROP TRIGGER IF EXISTS test_reject_ledger_insert "
                    "ON customer_ledger_entries"
                )
            )
            await connection.execute(text("DROP FUNCTION IF EXISTS test_reject_ledger_insert()"))
        await engine.dispose()
    saved_sale = await client.get(f"/api/v1/sales/{sale['id']}", headers=headers)
    assert saved_sale.json()["status"] == "DRAFT"
    stock = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert stock.json()["available_quantity"] == "5.000"
    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers
    )
    assert ledger.json()["items"] == []


async def test_missing_projection_is_reported_as_corrupt_state(
    client: AsyncClient, test_settings: Settings
) -> None:
    headers = await _signup(client, "corrupt")
    customer = await _customer(client, headers, "Corrupt Ledger")
    product = await _product(client, headers, "Corrupt Product")
    await _stock(client, headers, product["id"])
    sale = await _draft(
        client, headers, customer["id"], product, "1", key="corrupt-draft"
    )
    assert (await _post(client, headers, sale["id"], "corrupt-post")).status_code == 200
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "DELETE FROM customer_balance_projections "
                "WHERE customer_id = :customer_id"
            ),
            {"customer_id": customer["id"]},
        )
    await engine.dispose()
    retry = await _post(client, headers, sale["id"], "corrupt-post")
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "LEDGER_STATE_CORRUPT"
    summary = await client.get(
        f"/api/v1/customers/{customer['id']}/financial-summary", headers=headers
    )
    assert summary.status_code == 409
    assert summary.json()["error"]["code"] == "LEDGER_STATE_CORRUPT"


async def test_ledger_entries_cannot_be_updated_or_deleted(
    client: AsyncClient, test_settings: Settings
) -> None:
    headers = await _signup(client, "immutable")
    customer = await _customer(client, headers, "Immutable Ledger")
    product = await _product(client, headers, "Immutable Product")
    await _stock(client, headers, product["id"])
    sale = await _draft(
        client, headers, customer["id"], product, "1", key="immutable-draft"
    )
    assert (await _post(client, headers, sale["id"], "immutable-post")).status_code == 200
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    with pytest.raises(DBAPIError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE customer_ledger_entries SET debit = 1 "
                    "WHERE reference_id = :sale_id"
                ),
                {"sale_id": sale["id"]},
            )
    with pytest.raises(DBAPIError):
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM customer_ledger_entries WHERE reference_id = :sale_id"),
                {"sale_id": sale["id"]},
            )
    async with engine.connect() as connection:
        count = await connection.scalar(
            text("SELECT count(*) FROM customer_ledger_entries WHERE reference_id = :sale_id"),
            {"sale_id": sale["id"]},
        )
    await engine.dispose()
    assert count == 1


async def test_ledger_validation_errors_are_actionable(client: AsyncClient) -> None:
    headers = await _signup(client, "validation")
    customer = await _customer(client, headers, "Validation Ledger")
    cases = (
        (
            "/api/v1/customers/not-a-customer/ledger",
            "customer_id",
            "Open the customer from the customer list and try again.",
        ),
        (
            f"/api/v1/customers/{customer['id']}/ledger?date=not-a-date",
            "date",
            "Enter the ledger date as YYYY-MM-DD.",
        ),
        (
            f"/api/v1/customers/{customer['id']}/ledger?entry_type=refund",
            "entry_type",
            "Choose All Entries, Sales, Reversals, Payments, or Payment Reversals.",
        ),
    )
    for path, field, message in cases:
        response = await client.get(path, headers=headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert response.json()["error"]["field_errors"][field] == message


async def test_ledger_endpoints_require_authentication(client: AsyncClient) -> None:
    customer_id = uuid4()
    for path in (
        f"/api/v1/customers/{customer_id}/financial-summary",
        f"/api/v1/customers/{customer_id}/ledger",
        f"/api/v1/customers/{customer_id}/ledger/search?q=SALE-000001",
    ):
        response = await client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
