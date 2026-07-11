import asyncio
from datetime import date
from typing import Any
from uuid import uuid4

from httpx import AsyncClient


async def _signup(
    client: AsyncClient, suffix: str = "invoices"
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Invoices {suffix}",
            "email": f"invoices-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def _customer(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    phone: str | None = "+91 98765 43210",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": name,
            "phone": phone,
            "address_line_1": "Market Road",
            "city": "Kochi",
            "state": "Kerala",
            "postal_code": "682001",
        },
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
            "low_stock_threshold": "0",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]


async def _stock(
    client: AsyncClient,
    headers: dict[str, str],
    product_id: str,
    quantity: str = "100",
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
    quantity: str = "1",
    name: str = "Invoice Product",
    key_prefix: str = "invoice-sale",
) -> tuple[dict[str, Any], dict[str, Any]]:
    product = await _product(client, headers, f"{name} {key_prefix}", price=amount)
    await _stock(client, headers, product["id"])
    draft = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": f"{key_prefix}-draft"},
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": quantity,
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
    return posted.json()["sale"], product


async def _invoice(
    client: AsyncClient,
    headers: dict[str, str],
    sale_id: str,
    *,
    key: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/invoices",
        headers={**headers, "Idempotency-Key": key},
        json={"sale_id": sale_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["invoice"]


async def _issue(
    client: AsyncClient,
    headers: dict[str, str],
    invoice_id: str,
    *,
    key: str,
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/invoices/{invoice_id}/issue",
        headers={**headers, "Idempotency-Key": key},
    )
    assert response.status_code == 200, response.text
    return response.json()["invoice"]


async def _payment(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    amount: str,
    *,
    key: str,
    allocations: list[dict[str, str]] | None = None,
) -> Any:
    return await client.post(
        "/api/v1/payments",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "payment_date": date.today().isoformat(),
            "amount": amount,
            "payment_method": "cash",
            "allocations": allocations or [],
        },
    )


async def test_invoice_currency_is_snapshotted_from_business_settings(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "currency")
    settings = await client.patch(
        "/api/v1/business/settings", headers=headers, json={"currency": "USD"}
    )
    assert settings.status_code == 200, settings.text

    customer = await _customer(client, headers, "Currency Store")
    sale, _ = await _posted_sale(
        client, headers, customer["id"], amount="75", key_prefix="currency"
    )

    invoice = await _invoice(client, headers, sale["id"], key="currency-invoice")
    assert invoice["currency"] == "USD"
    issued = await _issue(client, headers, invoice["id"], key="currency-issue")
    assert issued["currency"] == "USD"

    changed = await client.patch(
        "/api/v1/business/settings", headers=headers, json={"currency": "EUR"}
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["error"]["code"] == "CURRENCY_CHANGE_RESTRICTED"
    historical = await client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers)
    assert historical.status_code == 200, historical.text
    assert historical.json()["currency"] == "USD"

    pdf = await client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert b"Amounts are shown in USD" in pdf.content


async def test_invoice_creation_issue_snapshot_and_pdf_download(client: AsyncClient) -> None:
    _, headers = await _signup(client, "snapshot")
    customer = await _customer(client, headers, "Snapshot Store")
    sale, product = await _posted_sale(
        client, headers, customer["id"], amount="42", key_prefix="snapshot"
    )

    draft = await _invoice(client, headers, sale["id"], key="snapshot-invoice")
    assert draft["invoice_number"] == "INV-000001"
    assert draft["status"] == "DRAFT"
    assert draft["sale_number"] == sale["sale_number"]
    assert draft["customer_name_snapshot"] == "Snapshot Store"
    assert draft["items"][0]["product_snapshot"].startswith("Invoice Product")

    issued = await _issue(client, headers, draft["id"], key="snapshot-issue")
    assert issued["status"] == "ISSUED"

    customer_update = await client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"name": "Renamed Store", "phone": "+91 90000 00000"},
    )
    assert customer_update.status_code == 200, customer_update.text
    product_update = await client.patch(
        f"/api/v1/products/{product['id']}",
        headers=headers,
        json={"name": "Renamed Product", "selling_price": "99"},
    )
    assert product_update.status_code == 200, product_update.text

    historical = await client.get(
        f"/api/v1/invoices/number/{issued['invoice_number']}", headers=headers
    )
    assert historical.status_code == 200, historical.text
    body = historical.json()
    assert body["customer_name_snapshot"] == "Snapshot Store"
    assert body["customer_phone_snapshot"] == "+91 98765 43210"
    assert body["items"][0]["product_snapshot"].startswith("Invoice Product")
    assert body["items"][0]["unit_snapshot"] == "piece"
    assert body["items"][0]["unit_price_snapshot"] == "42.00"

    pdf = await client.get(f"/api/v1/invoices/{issued['id']}/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-1.4")
    assert issued["invoice_number"].encode() in pdf.content


async def test_invoice_duplicate_validation_and_search_pagination(client: AsyncClient) -> None:
    _, headers = await _signup(client, "search")
    customer = await _customer(client, headers, "Searchable Customer")
    sale_a, _ = await _posted_sale(client, headers, customer["id"], amount="10", key_prefix="s-a")
    sale_b, _ = await _posted_sale(client, headers, customer["id"], amount="11", key_prefix="s-b")
    sale_c, _ = await _posted_sale(client, headers, customer["id"], amount="12", key_prefix="s-c")
    first = await _invoice(client, headers, sale_a["id"], key="invoice-a")
    await _invoice(client, headers, sale_b["id"], key="invoice-b")
    await _invoice(client, headers, sale_c["id"], key="invoice-c")

    duplicate = await client.post(
        "/api/v1/invoices",
        headers={**headers, "Idempotency-Key": "invoice-duplicate"},
        json={"sale_id": sale_a["id"]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVOICE_ALREADY_EXISTS"

    page = await client.get("/api/v1/invoices", headers=headers, params={"limit": 2})
    assert page.status_code == 200, page.text
    assert page.json()["has_more"] is True
    assert page.json()["next_cursor"]

    search = await client.get(
        "/api/v1/invoices/search",
        headers=headers,
        params={"q": "Searchable", "limit": 10},
    )
    assert search.status_code == 200, search.text
    assert {item["invoice_number"] for item in search.json()["items"]} >= {
        first["invoice_number"]
    }

    by_customer = await client.get(
        f"/api/v1/customers/{customer['id']}/invoices", headers=headers
    )
    assert by_customer.status_code == 200, by_customer.text
    assert by_customer.json()["page_size"] == 3


async def test_payment_allocation_to_invoice_and_customer_credit_auto_application(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "allocation")
    customer = await _customer(client, headers, "Invoice Allocation Customer")
    sale, _ = await _posted_sale(client, headers, customer["id"], amount="80", key_prefix="alloc")
    issued = await _issue(
        client,
        headers,
        (await _invoice(client, headers, sale["id"], key="alloc-invoice"))["id"],
        key="alloc-issue",
    )

    paid = await _payment(
        client,
        headers,
        customer["id"],
        "30",
        key="invoice-allocation-payment",
        allocations=[{"invoice_id": issued["id"], "allocated_amount": "30"}],
    )
    assert paid.status_code == 201, paid.text
    payment = paid.json()["payment"]
    assert payment["allocations"][0]["invoice_id"] == issued["id"]
    assert payment["allocations"][0]["reference_type"] == "INVOICE"
    assert payment["allocations"][0]["reference"] == issued["invoice_number"]

    invoice_after_payment = await client.get(
        f"/api/v1/invoices/{issued['id']}", headers=headers
    )
    assert invoice_after_payment.json()["allocated_amount"] == "30.00"
    assert invoice_after_payment.json()["outstanding_amount"] == "50.00"
    pdf_after_payment = await client.get(
        f"/api/v1/invoices/{issued['id']}/pdf", headers=headers
    )
    assert pdf_after_payment.status_code == 200, pdf_after_payment.text
    assert b"Allocated payments" in pdf_after_payment.content
    assert b"INR 30.00" in pdf_after_payment.content
    assert b"Outstanding balance" in pdf_after_payment.content
    assert b"INR 50.00" in pdf_after_payment.content

    credit_customer = await _customer(client, headers, "Credit Before Invoice")
    credit_payment = await _payment(
        client, headers, credit_customer["id"], "100", key="future-credit"
    )
    assert credit_payment.status_code == 201, credit_payment.text
    credit_sale, _ = await _posted_sale(
        client, headers, credit_customer["id"], amount="60", key_prefix="credit-invoice"
    )
    credit_invoice = await _invoice(
        client, headers, credit_sale["id"], key="credit-invoice-create"
    )
    issued_credit_invoice = await _issue(
        client, headers, credit_invoice["id"], key="credit-invoice-issue"
    )
    assert issued_credit_invoice["allocated_amount"] == "60.00"
    assert issued_credit_invoice["outstanding_amount"] == "0.00"
    credit = await client.get(
        f"/api/v1/customers/{credit_customer['id']}/credit", headers=headers
    )
    assert credit.json()["available_credit"] == "40.00"


async def test_invoice_void_uses_existing_sale_reversal_and_is_idempotent(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "void")
    customer = await _customer(client, headers, "Void Invoice Customer")
    sale, _ = await _posted_sale(client, headers, customer["id"], amount="25", key_prefix="void")
    invoice = await _issue(
        client,
        headers,
        (await _invoice(client, headers, sale["id"], key="void-invoice"))["id"],
        key="void-issue",
    )

    first = await client.post(
        f"/api/v1/invoices/{invoice['id']}/void",
        headers={**headers, "Idempotency-Key": "void-invoice-key"},
    )
    duplicate = await client.post(
        f"/api/v1/invoices/{invoice['id']}/void",
        headers={**headers, "Idempotency-Key": "void-invoice-key"},
    )
    assert first.status_code == duplicate.status_code == 200
    assert first.json()["invoice"]["status"] == "VOID"

    sale_after = await client.get(f"/api/v1/sales/{sale['id']}", headers=headers)
    assert sale_after.status_code == 200, sale_after.text
    assert sale_after.json()["status"] == "VOID"
    ledger = await client.get(
        f"/api/v1/customers/{customer['id']}/ledger",
        headers=headers,
        params={"entry_type": "reversal"},
    )
    assert ledger.status_code == 200, ledger.text
    assert ledger.json()["items"][0]["reference"] == sale["sale_number"]


async def test_invoice_numbering_is_concurrency_safe(client: AsyncClient) -> None:
    _, headers = await _signup(client, "concurrent")
    customer = await _customer(client, headers, "Concurrent Invoice Customer")
    sale_a, _ = await _posted_sale(client, headers, customer["id"], amount="13", key_prefix="c-a")
    sale_b, _ = await _posted_sale(client, headers, customer["id"], amount="14", key_prefix="c-b")

    responses = await asyncio.gather(
        client.post(
            "/api/v1/invoices",
            headers={**headers, "Idempotency-Key": "concurrent-invoice-a"},
            json={"sale_id": sale_a["id"]},
        ),
        client.post(
            "/api/v1/invoices",
            headers={**headers, "Idempotency-Key": "concurrent-invoice-b"},
            json={"sale_id": sale_b["id"]},
        ),
    )
    assert all(response.status_code == 201 for response in responses)
    assert {response.json()["invoice"]["invoice_number"] for response in responses} == {
        "INV-000001",
        "INV-000002",
    }


async def test_invoice_cross_tenant_access_and_allocation_are_rejected(
    client: AsyncClient,
) -> None:
    _, headers_a = await _signup(client, "tenant-a")
    _, headers_b = await _signup(client, "tenant-b")
    customer_a = await _customer(client, headers_a, "Tenant A Customer")
    sale_a, _ = await _posted_sale(client, headers_a, customer_a["id"], key_prefix="tenant-a")
    invoice_a = await _issue(
        client,
        headers_a,
        (await _invoice(client, headers_a, sale_a["id"], key="tenant-a-invoice"))["id"],
        key="tenant-a-issue",
    )
    customer_b = await _customer(client, headers_b, "Tenant B Customer")

    denied = await client.get(f"/api/v1/invoices/{invoice_a['id']}", headers=headers_b)
    assert denied.status_code == 404
    denied_pdf = await client.get(
        f"/api/v1/invoices/{invoice_a['id']}/pdf", headers=headers_b
    )
    assert denied_pdf.status_code == 404
    allocation = await _payment(
        client,
        headers_b,
        customer_b["id"],
        "5",
        key="cross-tenant-invoice-allocation",
        allocations=[{"invoice_id": invoice_a["id"], "allocated_amount": "5"}],
    )
    assert allocation.status_code == 404
    assert allocation.json()["error"]["code"] == "PAYMENT_ALLOCATION_TARGET_NOT_FOUND"


async def test_invoice_validation_errors_are_friendly(client: AsyncClient) -> None:
    _, headers = await _signup(client, "validation")
    missing = await client.post(
        "/api/v1/invoices",
        headers={**headers, "Idempotency-Key": "missing-sale"},
        json={"sale_id": str(uuid4())},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SALE_NOT_FOUND"
    assert "Select a posted sale" in missing.json()["error"]["field_errors"]["sale_id"]

    customer = await _customer(client, headers, "Archived Invoice Customer")
    sale, _ = await _posted_sale(
        client, headers, customer["id"], amount="15", key_prefix="archived"
    )
    archived = await client.post(f"/api/v1/customers/{customer['id']}/archive", headers=headers)
    assert archived.status_code == 200, archived.text
    invoice = await client.post(
        "/api/v1/invoices",
        headers={**headers, "Idempotency-Key": "archived-invoice"},
        json={"sale_id": sale["id"]},
    )
    assert invoice.status_code == 422
    assert invoice.json()["error"]["code"] == "CUSTOMER_ARCHIVED"
