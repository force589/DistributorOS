import asyncio
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from distributoros.core.config import Settings
from distributoros.modules.ledger.reconciliation import LedgerReconciliationService


async def _signup(
    client: AsyncClient, suffix: str = "payments"
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Payments {suffix}",
            "email": f"payments-{suffix}@example.com",
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


async def _posted_sale(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    *,
    amount: str = "50",
    key_prefix: str = "payment-sale",
) -> dict[str, Any]:
    product = await _product(client, headers, f"Product {key_prefix}", amount)
    await _stock(client, headers, product["id"])
    draft = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": f"{key_prefix}-draft"},
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": "1",
                    "unit_price": amount,
                }
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    posted = await client.post(
        f"/api/v1/sales/{draft.json()['sale']['id']}/post",
        headers={**headers, "Idempotency-Key": f"{key_prefix}-post"},
    )
    assert posted.status_code == 200, posted.text
    return posted.json()["sale"]


async def _payment(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    amount: str,
    *,
    key: str,
    method: str = "cash",
    reference: str | None = None,
    allocations: list[dict[str, str]] | None = None,
) -> Any:
    return await client.post(
        "/api/v1/payments",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "payment_date": date.today().isoformat(),
            "amount": amount,
            "payment_method": method,
            "reference_number": reference,
            "notes": "Phase 6 test payment",
            "allocations": allocations or [],
        },
    )


async def _sale_ledger_entry_id(
    client: AsyncClient, headers: dict[str, str], customer_id: str
) -> str:
    ledger = await client.get(
        f"/api/v1/customers/{customer_id}/ledger",
        headers=headers,
        params={"entry_type": "sale"},
    )
    assert ledger.status_code == 200, ledger.text
    return ledger.json()["items"][0]["id"]


def _admin_engine(settings: Settings) -> AsyncEngine:
    assert settings.database_admin_url is not None
    return create_async_engine(settings.database_admin_url)


async def test_payment_posting_reduces_outstanding_and_creates_ledger_credit(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "posting")
    customer = await _customer(client, headers, "Payment Customer")
    await _posted_sale(client, headers, customer["id"], amount="75", key_prefix="post-one")

    response = await _payment(
        client,
        headers,
        customer["id"],
        "25",
        key="payment-post-one",
        method="upi",
        reference="UPI-123",
    )
    assert response.status_code == 201, response.text
    payment = response.json()["payment"]
    assert payment["payment_number"] == "PAY-000001"
    assert payment["status"] == "POSTED"
    assert payment["payment_method"] == "upi"
    assert payment["amount"] == "25.00"

    balance = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers
    )
    assert balance.status_code == 200, balance.text
    assert balance.json()["outstanding_balance"] == "50.00"
    assert balance.json()["available_credit"] == "0.00"
    assert balance.json()["total_payments"] == "25.00"

    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers
    )
    assert ledger.status_code == 200, ledger.text
    assert ledger.json()["items"][0]["entry_type"] == "PAYMENT"
    assert ledger.json()["items"][0]["reference"] == "PAY-000001"
    assert ledger.json()["items"][0]["credit"] == "25.00"
    assert ledger.json()["items"][0]["running_balance"] == "50.00"


async def test_overpayment_creates_customer_credit_without_negative_outstanding(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "credit")
    customer = await _customer(client, headers, "Credit Customer")
    await _posted_sale(client, headers, customer["id"], amount="40", key_prefix="credit-sale")
    paid = await _payment(
        client, headers, customer["id"], "55", key="credit-payment", method="cash"
    )
    assert paid.status_code == 201, paid.text

    credit = await client.get(
        f"/api/v1/customers/{customer['id']}/credit", headers=headers
    )
    balance = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers
    )
    assert credit.json()["available_credit"] == "15.00"
    assert balance.json()["outstanding_balance"] == "0.00"
    assert balance.json()["available_credit"] == "15.00"

    await _posted_sale(client, headers, customer["id"], amount="10", key_prefix="credit-next")
    balance_after_sale = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers
    )
    assert balance_after_sale.json()["outstanding_balance"] == "0.00"
    assert balance_after_sale.json()["available_credit"] == "5.00"


async def test_payment_allocation_is_immutable_and_validated(client: AsyncClient) -> None:
    _, headers = await _signup(client, "allocation")
    customer = await _customer(client, headers, "Allocation Customer")
    await _posted_sale(client, headers, customer["id"], amount="60", key_prefix="alloc-sale")
    ledger_entry_id = await _sale_ledger_entry_id(client, headers, customer["id"])

    response = await _payment(
        client,
        headers,
        customer["id"],
        "35",
        key="allocated-payment",
        allocations=[{"ledger_entry_id": ledger_entry_id, "allocated_amount": "35"}],
    )
    assert response.status_code == 201, response.text
    payment = response.json()["payment"]
    assert payment["allocated_amount"] == "35.00"
    assert payment["unallocated_amount"] == "0.00"
    assert payment["allocations"][0]["ledger_entry_id"] == ledger_entry_id
    assert payment["allocations"][0]["reference"].startswith("SALE-")

    duplicate_target = await _payment(
        client,
        headers,
        customer["id"],
        "5",
        key="duplicate-allocation",
        allocations=[
            {"ledger_entry_id": ledger_entry_id, "allocated_amount": "1"},
            {"ledger_entry_id": ledger_entry_id, "allocated_amount": "1"},
        ],
    )
    assert duplicate_target.status_code == 422
    assert duplicate_target.json()["error"]["code"] == "DUPLICATE_PAYMENT_ALLOCATION"

    too_much = await _payment(
        client,
        headers,
        customer["id"],
        "10",
        key="too-much-allocation",
        allocations=[{"ledger_entry_id": ledger_entry_id, "allocated_amount": "30"}],
    )
    assert too_much.status_code == 422
    assert too_much.json()["error"]["code"] == "PAYMENT_ALLOCATION_TOTAL_INVALID"


async def test_payment_void_creates_reversal_and_is_idempotent(client: AsyncClient) -> None:
    _, headers = await _signup(client, "void")
    customer = await _customer(client, headers, "Void Customer")
    await _posted_sale(client, headers, customer["id"], amount="100", key_prefix="void-sale")
    payment = (
        await _payment(client, headers, customer["id"], "70", key="void-payment")
    ).json()["payment"]

    first = await client.post(
        f"/api/v1/payments/{payment['id']}/void",
        headers={**headers, "Idempotency-Key": "void-payment-key"},
    )
    duplicate = await client.post(
        f"/api/v1/payments/{payment['id']}/void",
        headers={**headers, "Idempotency-Key": "void-payment-key"},
    )
    assert first.status_code == duplicate.status_code == 200
    assert first.json()["payment"]["status"] == "VOID"

    conflict = await client.post(
        f"/api/v1/payments/{payment['id']}/void",
        headers={**headers, "Idempotency-Key": "different-void-key"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "PAYMENT_ALREADY_VOIDED"

    balance = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers
    )
    assert balance.json()["outstanding_balance"] == "100.00"
    assert balance.json()["total_payments"] == "0.00"
    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers
    )
    assert [item["entry_type"] for item in ledger.json()["items"][:2]] == [
        "PAYMENT_REVERSAL",
        "PAYMENT",
    ]


async def test_duplicate_idempotency_and_concurrent_posting_are_safe(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "concurrent")
    customer = await _customer(client, headers, "Concurrent Payment Customer")
    await _posted_sale(client, headers, customer["id"], amount="100", key_prefix="concurrent-sale")

    duplicate_payload = await asyncio.gather(
        _payment(client, headers, customer["id"], "15", key="same-payment-key"),
        _payment(client, headers, customer["id"], "15", key="same-payment-key"),
    )
    assert all(response.status_code == 201 for response in duplicate_payload)
    assert {
        response.json()["payment"]["id"] for response in duplicate_payload
    } == {duplicate_payload[0].json()["payment"]["id"]}

    different_payload = await _payment(
        client, headers, customer["id"], "20", key="same-payment-key"
    )
    assert different_payload.status_code == 409
    assert different_payload.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    responses = await asyncio.gather(
        _payment(client, headers, customer["id"], "10", key="concurrent-a"),
        _payment(client, headers, customer["id"], "12", key="concurrent-b"),
    )
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["payment"]["payment_number"] for response in responses}) == 2
    balance = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers
    )
    assert balance.json()["outstanding_balance"] == "63.00"


async def test_concurrent_voiding_does_not_duplicate_reversal(client: AsyncClient) -> None:
    _, headers = await _signup(client, "concurrent-void")
    customer = await _customer(client, headers, "Concurrent Void Customer")
    await _posted_sale(client, headers, customer["id"], amount="30", key_prefix="cv-sale")
    payment = (
        await _payment(client, headers, customer["id"], "20", key="cv-payment")
    ).json()["payment"]
    responses = await asyncio.gather(
        client.post(
            f"/api/v1/payments/{payment['id']}/void",
            headers={**headers, "Idempotency-Key": "same-void-key"},
        ),
        client.post(
            f"/api/v1/payments/{payment['id']}/void",
            headers={**headers, "Idempotency-Key": "same-void-key"},
        ),
    )
    assert all(response.status_code == 200 for response in responses)
    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger",
        headers=headers,
        params={"entry_type": "payment_reversal"},
    )
    assert len(ledger.json()["items"]) == 1


async def test_payment_search_pagination_and_customer_history(client: AsyncClient) -> None:
    _, headers = await _signup(client, "search")
    customer = await _customer(client, headers, "Search Payment Customer")
    await _posted_sale(client, headers, customer["id"], amount="100", key_prefix="search-sale")
    for index, method in enumerate(("cash", "upi", "bank_transfer")):
        response = await _payment(
            client,
            headers,
            customer["id"],
            "5",
            key=f"search-payment-{index}",
            method=method,
            reference=f"REF-{index}",
        )
        assert response.status_code == 201, response.text

    first = await client.get("/api/v1/payments", headers=headers, params={"limit": 2})
    second = await client.get(
        "/api/v1/payments",
        headers=headers,
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert first.json()["has_more"] is True
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 1

    by_reference = await client.get(
        "/api/v1/payments/search", headers=headers, params={"q": "REF-1"}
    )
    assert [item["reference_number"] for item in by_reference.json()["items"]] == ["REF-1"]
    by_method = await client.get(
        "/api/v1/payments/search",
        headers=headers,
        params={"method": "bank_transfer"},
    )
    assert [item["payment_method"] for item in by_method.json()["items"]] == [
        "bank_transfer"
    ]
    history = await client.get(
        f"/api/v1/customers/{customer['id']}/payments", headers=headers
    )
    assert len(history.json()["items"]) == 3


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        (
            {"amount": "0", "payment_method": "cash"},
            "amount",
            "Payment amount must be greater than zero.",
        ),
        (
            {"amount": "-1", "payment_method": "cash"},
            "amount",
            "Payment amount must be greater than zero.",
        ),
        (
            {"amount": "1", "payment_method": "crypto"},
            "payment_method",
            "Choose Cash, UPI, Bank Transfer, Cheque, or Other.",
        ),
    ],
)
async def test_payment_validation_errors_are_actionable(
    client: AsyncClient,
    payload: dict[str, str],
    field: str,
    message: str,
) -> None:
    _, headers = await _signup(client, f"validation-{field}-{payload['amount']}")
    customer = await _customer(client, headers, f"Validation {field}")
    response = await client.post(
        "/api/v1/payments",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "customer_id": customer["id"],
            "payment_date": date.today().isoformat(),
            **payload,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["field_errors"][field] == message


async def test_archived_unknown_and_cross_tenant_customers_are_rejected(
    client: AsyncClient,
) -> None:
    _, first_headers = await _signup(client, "tenant-a")
    _, second_headers = await _signup(client, "tenant-b")
    first_customer = await _customer(client, first_headers, "Tenant A Customer")
    second_customer = await _customer(client, second_headers, "Tenant B Customer")
    await _posted_sale(
        client, first_headers, first_customer["id"], amount="20", key_prefix="tenant-a-sale"
    )
    first_ledger_id = await _sale_ledger_entry_id(
        client, first_headers, first_customer["id"]
    )
    first_payment = (
        await _payment(
            client,
            first_headers,
            first_customer["id"],
            "5",
            key="tenant-a-payment",
        )
    ).json()["payment"]

    cross_get = await client.get(
        f"/api/v1/payments/{first_payment['id']}", headers=second_headers
    )
    assert cross_get.status_code == 404

    cross_customer = await _payment(
        client,
        second_headers,
        first_customer["id"],
        "5",
        key="cross-customer-payment",
    )
    assert cross_customer.status_code == 404
    assert cross_customer.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"

    cross_allocation = await _payment(
        client,
        second_headers,
        second_customer["id"],
        "5",
        key="cross-allocation-payment",
        allocations=[{"ledger_entry_id": first_ledger_id, "allocated_amount": "5"}],
    )
    assert cross_allocation.status_code == 404
    assert cross_allocation.json()["error"]["code"] == "PAYMENT_ALLOCATION_TARGET_NOT_FOUND"

    await client.post(f"/api/v1/customers/{second_customer['id']}/archive", headers=second_headers)
    archived = await _payment(
        client,
        second_headers,
        second_customer["id"],
        "5",
        key="archived-customer-payment",
    )
    assert archived.status_code == 422
    assert archived.json()["error"]["code"] == "CUSTOMER_ARCHIVED"


async def test_payment_reconciliation_and_projection_rebuild(
    client: AsyncClient, test_settings: Settings
) -> None:
    _, headers = await _signup(client, "reconciliation")
    customer = await _customer(client, headers, "Reconciliation Payment Customer")
    await _posted_sale(client, headers, customer["id"], amount="50", key_prefix="recon-sale")
    payment = await _payment(
        client, headers, customer["id"], "60", key="recon-payment", method="cheque"
    )
    assert payment.status_code == 201, payment.text

    engine = _admin_engine(test_settings)
    try:
        service = LedgerReconciliationService(engine)
        clean = await service.reconcile()
        assert clean.is_consistent
        assert clean.entry_count == 2
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE customer_balance_projections
                    SET outstanding_balance = 999,
                        available_credit = 0,
                        total_payments = 999
                    WHERE customer_id = :customer_id
                    """
                ),
                {"customer_id": customer["id"]},
            )
        mismatch = await service.reconcile()
        assert not mismatch.is_consistent
        assert len(mismatch.balance_mismatches) == 1
        rebuilt = await service.rebuild()
        assert rebuilt.after.is_consistent
    finally:
        await engine.dispose()
    balance = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers
    )
    assert balance.json()["outstanding_balance"] == "0.00"
    assert balance.json()["available_credit"] == "10.00"


async def test_payment_ledger_timestamps_are_utc(client: AsyncClient) -> None:
    _, headers = await _signup(client, "utc")
    customer = await _customer(client, headers, "UTC Payment Customer")
    response = await _payment(client, headers, customer["id"], "10", key="utc-payment")
    assert response.status_code == 201, response.text
    created_at = datetime.fromisoformat(response.json()["payment"]["created_at"])
    assert created_at.tzinfo is not None
    assert created_at.astimezone(UTC).utcoffset().total_seconds() == 0
