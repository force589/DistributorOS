from __future__ import annotations

from datetime import date
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings
from distributoros.core.database import set_internal_maintenance_context
from distributoros.modules.inventory.reconciliation import InventoryReconciliationService
from distributoros.modules.ledger.reconciliation import LedgerReconciliationService


async def _signup(
    client: AsyncClient, suffix: str
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Phase 7.5 {suffix}",
            "email": f"phase-7-5-{suffix}@example.com",
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
        "/api/v1/customers",
        headers=headers,
        json={
            "name": name,
            "phone": "+91 98765 43210",
            "email": f"{name.lower().replace(' ', '.')}@example.com",
            "address_line_1": "Market Road",
            "city": "Kochi",
            "state": "Kerala",
            "postal_code": "682001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["customer"]  # type: ignore[no-any-return]


async def _product(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    sku: str,
    barcode: str,
    price: str = "10",
    threshold: str = "2",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "sku": sku,
            "barcode": barcode,
            "selling_price": price,
            "unit": "piece",
            "low_stock_threshold": threshold,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]  # type: ignore[no-any-return]


async def _movement(
    client: AsyncClient,
    headers: dict[str, str],
    path: str,
    product_id: str,
    quantity: str,
    *,
    key: str,
    extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/inventory/{path}",
        headers={**headers, "Idempotency-Key": key},
        json={"product_id": product_id, "quantity": quantity, **(extra or {})},
    )
    assert response.status_code == 201, response.text
    return response.json()["movement"]  # type: ignore[no-any-return]


async def _sale(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    product_id: str,
    quantity: str,
    price: str,
    *,
    key: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product_id, "quantity": quantity, "unit_price": price}
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["sale"]  # type: ignore[no-any-return]


async def _post_sale(
    client: AsyncClient, headers: dict[str, str], sale_id: str, *, key: str
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/sales/{sale_id}/post",
        headers={**headers, "Idempotency-Key": key},
    )
    assert response.status_code == 200, response.text
    return response.json()["sale"]  # type: ignore[no-any-return]


async def _invoice(
    client: AsyncClient, headers: dict[str, str], sale_id: str, *, key: str
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/invoices",
        headers={**headers, "Idempotency-Key": key},
        json={"sale_id": sale_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["invoice"]  # type: ignore[no-any-return]


async def _issue_invoice(
    client: AsyncClient, headers: dict[str, str], invoice_id: str, *, key: str
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/invoices/{invoice_id}/issue",
        headers={**headers, "Idempotency-Key": key},
    )
    assert response.status_code == 200, response.text
    return response.json()["invoice"]  # type: ignore[no-any-return]


async def _payment(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    amount: str,
    *,
    key: str,
    allocations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/payments",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "payment_date": date.today().isoformat(),
            "amount": amount,
            "payment_method": "upi",
            "reference_number": key.upper(),
            "allocations": allocations or [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["payment"]  # type: ignore[no-any-return]


async def test_phase_7_5_complete_release_journey(
    client: AsyncClient, test_settings: Settings
) -> None:
    session_a, headers_a = await _signup(client, "business-a")
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "phase-7-5-business-a@example.com", "password": "secure-pass-123"},
    )
    assert login_a.status_code == 200, login_a.text
    assert login_a.json()["user"]["business"]["id"] == session_a["user"]["business"]["id"]

    invalid_token = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"}
    )
    assert invalid_token.status_code == 401
    assert invalid_token.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert "traceback" not in invalid_token.text.lower()
    missing_token = await client.get("/api/v1/customers")
    assert missing_token.status_code == 401

    customer = await _customer(client, headers_a, "Release Store")
    duplicate_customer = await client.post(
        "/api/v1/customers", headers=headers_a, json={"name": "Release Store"}
    )
    assert duplicate_customer.status_code == 409
    case_duplicate_customer = await client.post(
        "/api/v1/customers", headers=headers_a, json={"name": "release store"}
    )
    assert case_duplicate_customer.status_code == 409
    invalid_customer = await client.post(
        "/api/v1/customers",
        headers=headers_a,
        json={"name": "", "email": "not-email", "phone": "abc"},
    )
    assert invalid_customer.status_code == 422
    assert invalid_customer.json()["error"]["field_errors"]["name"] == (
        "Customer name is required."
    )

    edited_customer = await client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers_a,
        json={"notes": "Morning route"},
    )
    assert edited_customer.status_code == 200, edited_customer.text
    archived_customer = await client.post(
        f"/api/v1/customers/{customer['id']}/archive", headers=headers_a
    )
    assert archived_customer.status_code == 200, archived_customer.text
    restored_customer = await client.post(
        f"/api/v1/customers/{customer['id']}/restore", headers=headers_a
    )
    assert restored_customer.status_code == 200, restored_customer.text

    product = await _product(
        client,
        headers_a,
        "Release Mango",
        sku="MANGO-1",
        barcode="890000000001",
        price="10",
    )
    duplicate_product = await client.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "release mango",
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "1",
        },
    )
    assert duplicate_product.status_code == 409
    duplicate_sku = await client.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "Another Mango",
            "sku": "mango-1",
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "1",
        },
    )
    assert duplicate_sku.status_code == 409
    duplicate_barcode = await client.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "Barcode Mango",
            "barcode": "890000000001",
            "selling_price": "10",
            "unit": "piece",
            "low_stock_threshold": "1",
        },
    )
    assert duplicate_barcode.status_code == 409
    invalid_product = await client.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "Invalid Product",
            "selling_price": "-1",
            "unit": "crate",
            "low_stock_threshold": "-1",
        },
    )
    assert invalid_product.status_code == 422
    assert "selling_price" in invalid_product.json()["error"]["field_errors"]
    archived_product = await client.post(
        f"/api/v1/products/{product['id']}/archive", headers=headers_a
    )
    assert archived_product.status_code == 200, archived_product.text
    restored_product = await client.post(
        f"/api/v1/products/{product['id']}/restore", headers=headers_a
    )
    assert restored_product.status_code == 200, restored_product.text

    await _movement(
        client, headers_a, "opening-stock", product["id"], "20", key="e2e-opening"
    )
    await _movement(
        client, headers_a, "stock-receipts", product["id"], "10", key="e2e-receipt"
    )
    await _movement(
        client,
        headers_a,
        "adjustments",
        product["id"],
        "-2",
        key="e2e-adjust",
        extra={"reason": "Cycle count"},
    )
    await _movement(client, headers_a, "damage", product["id"], "1", key="e2e-damage")
    await _movement(client, headers_a, "spoilage", product["id"], "0.5", key="e2e-spoil")
    await _movement(
        client, headers_a, "customer-returns", product["id"], "3", key="e2e-return"
    )
    stock = await client.get(f"/api/v1/inventory/stock/{product['id']}", headers=headers_a)
    assert stock.status_code == 200, stock.text
    assert stock.json()["available_quantity"] == "29.500"
    excessive_damage = await client.post(
        "/api/v1/inventory/damage",
        headers={**headers_a, "Idempotency-Key": "e2e-excessive-damage"},
        json={"product_id": product["id"], "quantity": "1000"},
    )
    assert excessive_damage.status_code == 409
    duplicate_receipt = await client.post(
        "/api/v1/inventory/stock-receipts",
        headers={**headers_a, "Idempotency-Key": "e2e-receipt"},
        json={"product_id": product["id"], "quantity": "10"},
    )
    assert duplicate_receipt.status_code == 201

    sale = await _sale(
        client,
        headers_a,
        customer["id"],
        product["id"],
        "5",
        "10",
        key="e2e-sale-draft",
    )
    edited_sale = await client.patch(
        f"/api/v1/sales/{sale['id']}",
        headers=headers_a,
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": product["id"], "quantity": "6", "unit_price": "10"}],
        },
    )
    assert edited_sale.status_code == 200, edited_sale.text
    posted_sale = await _post_sale(
        client, headers_a, sale["id"], key="e2e-sale-post"
    )
    assert posted_sale["subtotal"] == "60.00"
    stock_after_sale = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers_a
    )
    assert stock_after_sale.json()["available_quantity"] == "23.500"
    double_post = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers_a, "Idempotency-Key": "e2e-sale-post-again"},
    )
    assert double_post.status_code == 409
    edit_posted_sale = await client.patch(
        f"/api/v1/sales/{sale['id']}",
        headers=headers_a,
        json={"items": [{"product_id": product["id"], "quantity": "1", "unit_price": "10"}]},
    )
    assert edit_posted_sale.status_code == 409
    delete_sale = await client.delete(f"/api/v1/sales/{sale['id']}", headers=headers_a)
    assert delete_sale.status_code == 405

    invoice = await _invoice(client, headers_a, sale["id"], key="e2e-invoice")
    assert invoice["invoice_number"] == "INV-000001"
    issued_invoice = await _issue_invoice(
        client, headers_a, invoice["id"], key="e2e-invoice-issue"
    )
    assert issued_invoice["status"] == "ISSUED"
    assert issued_invoice["outstanding_amount"] == "60.00"

    renamed_customer = await client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers_a,
        json={"name": "Renamed Release Store"},
    )
    assert renamed_customer.status_code == 200, renamed_customer.text
    renamed_product = await client.patch(
        f"/api/v1/products/{product['id']}",
        headers=headers_a,
        json={"name": "Renamed Release Mango", "selling_price": "99"},
    )
    assert renamed_product.status_code == 200, renamed_product.text
    historical_invoice = await client.get(
        f"/api/v1/invoices/number/{issued_invoice['invoice_number']}",
        headers=headers_a,
    )
    assert historical_invoice.status_code == 200, historical_invoice.text
    assert historical_invoice.json()["customer_name_snapshot"] == "Release Store"
    assert historical_invoice.json()["items"][0]["product_snapshot"] == "Release Mango"
    assert historical_invoice.json()["items"][0]["unit_price_snapshot"] == "10.00"

    pdf = await client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=headers_a)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-1.4")

    direct_sale_void = await client.post(
        f"/api/v1/sales/{sale['id']}/void",
        headers={**headers_a, "Idempotency-Key": "e2e-direct-sale-void-invoiced"},
    )
    assert direct_sale_void.status_code == 409
    assert direct_sale_void.json()["error"]["code"] == "SALE_HAS_ISSUED_INVOICE"

    first_payment = await _payment(
        client,
        headers_a,
        customer["id"],
        "25",
        key="e2e-payment-partial",
        allocations=[{"invoice_id": invoice["id"], "allocated_amount": "25"}],
    )
    assert first_payment["allocated_amount"] == "25.00"
    invoice_after_partial = await client.get(
        f"/api/v1/invoices/{invoice['id']}", headers=headers_a
    )
    assert invoice_after_partial.json()["outstanding_amount"] == "35.00"
    duplicate_payment = await client.post(
        "/api/v1/payments",
        headers={**headers_a, "Idempotency-Key": "e2e-payment-partial"},
        json={
            "customer_id": customer["id"],
            "payment_date": date.today().isoformat(),
            "amount": "25",
            "payment_method": "upi",
            "reference_number": "E2E-PAYMENT-PARTIAL",
            "allocations": [{"invoice_id": invoice["id"], "allocated_amount": "25"}],
        },
    )
    assert duplicate_payment.status_code == 201
    assert duplicate_payment.json()["payment"]["id"] == first_payment["id"]

    second_payment = await _payment(
        client,
        headers_a,
        customer["id"],
        "35",
        key="e2e-payment-full",
        allocations=[{"invoice_id": invoice["id"], "allocated_amount": "35"}],
    )
    assert second_payment["unallocated_amount"] == "0.00"
    paid_invoice = await client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers_a)
    assert paid_invoice.json()["outstanding_amount"] == "0.00"

    void_invoice = await client.post(
        f"/api/v1/invoices/{invoice['id']}/void",
        headers={**headers_a, "Idempotency-Key": "e2e-invoice-void"},
    )
    assert void_invoice.status_code == 200, void_invoice.text
    assert void_invoice.json()["invoice"]["status"] == "VOID"
    assert void_invoice.json()["invoice"]["outstanding_amount"] == "0.00"
    voided_sale = await client.get(f"/api/v1/sales/{sale['id']}", headers=headers_a)
    assert voided_sale.json()["status"] == "VOID"
    restored_stock = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers_a
    )
    assert restored_stock.json()["available_quantity"] == "29.500"

    credit_sale = await _sale(
        client,
        headers_a,
        customer["id"],
        product["id"],
        "4",
        "10",
        key="e2e-credit-sale",
    )
    await _post_sale(client, headers_a, credit_sale["id"], key="e2e-credit-sale-post")
    credit_invoice = await _invoice(
        client, headers_a, credit_sale["id"], key="e2e-credit-invoice"
    )
    issued_credit_invoice = await _issue_invoice(
        client,
        headers_a,
        credit_invoice["id"],
        key="e2e-credit-invoice-issue",
    )
    assert issued_credit_invoice["allocated_amount"] == "40.00"
    assert issued_credit_invoice["outstanding_amount"] == "0.00"
    balance_after_credit_invoice = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers_a
    )
    assert balance_after_credit_invoice.json()["outstanding_balance"] == "0.00"
    assert balance_after_credit_invoice.json()["available_credit"] == "20.00"

    credit_payment = await _payment(
        client, headers_a, customer["id"], "5", key="e2e-extra-credit"
    )
    void_payment = await client.post(
        f"/api/v1/payments/{credit_payment['id']}/void",
        headers={**headers_a, "Idempotency-Key": "e2e-extra-credit-void"},
    )
    assert void_payment.status_code == 200, void_payment.text
    final_balance = await client.get(
        f"/api/v1/customers/{customer['id']}/balance", headers=headers_a
    )
    assert final_balance.json()["outstanding_balance"] == "0.00"
    assert final_balance.json()["available_credit"] == "20.00"
    assert final_balance.json()["total_payments"] == "60.00"

    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger", headers=headers_a
    )
    assert ledger.status_code == 200, ledger.text
    assert {item["entry_type"] for item in ledger.json()["items"]} >= {
        "SALE",
        "REVERSAL",
        "PAYMENT",
        "PAYMENT_REVERSAL",
    }

    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    try:
        inventory_report = await InventoryReconciliationService(engine).reconcile()
        assert inventory_report.is_consistent
        inventory_rebuild = await InventoryReconciliationService(engine).rebuild()
        assert inventory_rebuild.after.is_consistent
        ledger_report = await LedgerReconciliationService(engine).reconcile()
        assert ledger_report.is_consistent
        ledger_rebuild = await LedgerReconciliationService(engine).rebuild()
        assert ledger_rebuild.after.is_consistent
        async with engine.begin() as connection:
            await set_internal_maintenance_context(connection)
            orphan_counts = await connection.execute(
                text(
                    """
                    SELECT
                      (
                        SELECT count(*)
                        FROM invoices invoice
                        LEFT JOIN sales sale
                          ON sale.id = invoice.sale_id
                         AND sale.tenant_id = invoice.tenant_id
                        WHERE sale.id IS NULL
                      ) AS orphan_invoices,
                      (
                        SELECT count(*)
                        FROM payment_allocations allocation
                        LEFT JOIN customer_ledger_entries entry
                          ON entry.id = allocation.ledger_entry_id
                         AND entry.tenant_id = allocation.tenant_id
                        WHERE entry.id IS NULL
                      ) AS orphan_allocations,
                      (
                        SELECT count(*)
                        FROM stock_balances balance
                        LEFT JOIN products product
                          ON product.id = balance.product_id
                         AND product.tenant_id = balance.tenant_id
                        LEFT JOIN warehouses warehouse
                          ON warehouse.id = balance.warehouse_id
                         AND warehouse.tenant_id = balance.tenant_id
                        WHERE product.id IS NULL OR warehouse.id IS NULL
                      ) AS orphan_stock_balances
                    """
                )
            )
            row = orphan_counts.one()
            assert row.orphan_invoices == 0
            assert row.orphan_allocations == 0
            assert row.orphan_stock_balances == 0
    finally:
        await engine.dispose()

    session_b, headers_b = await _signup(client, "business-b")
    assert session_b["user"]["business"]["id"] != session_a["user"]["business"]["id"]
    assert (
        await client.get(f"/api/v1/customers/{customer['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/products/{product['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/sales/{sale['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/payments/{first_payment['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/customers/{customer['id']}/ledger", headers=headers_b
        )
    ).status_code == 404
    guessed_invoice = await client.get(
        f"/api/v1/invoices/number/{invoice['invoice_number']}", headers=headers_b
    )
    assert guessed_invoice.status_code == 404
    forged_tenant = await client.post(
        "/api/v1/customers",
        headers=headers_b,
        json={"name": "Forged Tenant", "tenant_id": session_a["user"]["business"]["id"]},
    )
    assert forged_tenant.status_code == 422

    logout = await client.post("/api/v1/auth/logout", headers=headers_a)
    assert logout.status_code == 200, logout.text
    revoked_session = await client.get("/api/v1/auth/me", headers=headers_a)
    assert revoked_session.status_code == 401
    replay_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]}
    )
    assert replay_refresh.status_code in {200, 401}
    if replay_refresh.status_code == 200:
        replayed_again = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]}
        )
        assert replayed_again.status_code == 401

    injection_search = await client.get(
        "/api/v1/customers/search",
        headers=headers_b,
        params={"q": "' OR 1=1 --"},
    )
    assert injection_search.status_code == 200
    assert injection_search.json()["items"] == []
    assert "traceback" not in injection_search.text.lower()
