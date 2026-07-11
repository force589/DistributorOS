from __future__ import annotations

from datetime import date
from typing import Any

from httpx import AsyncClient


async def _signup(client: AsyncClient, suffix: str) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Insights {suffix}",
            "email": f"insights-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def _customer(client: AsyncClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    response = await client.post("/api/v1/customers", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["customer"]


async def _product(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    price: str,
    threshold: str,
    sku: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "sku": sku,
            "selling_price": price,
            "unit": "piece",
            "low_stock_threshold": threshold,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]


async def _opening_stock(
    client: AsyncClient,
    headers: dict[str, str],
    product_id: str,
    quantity: str,
    key: str,
) -> None:
    response = await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": key},
        json={"product_id": product_id, "quantity": quantity},
    )
    assert response.status_code == 201, response.text


async def _sale(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    product_id: str,
    quantity: str,
    price: str,
    key: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/sales",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": price,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    sale = response.json()["sale"]
    posted = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": f"{key}-post"},
    )
    assert posted.status_code == 200, posted.text
    return posted.json()["sale"]


async def _invoice(
    client: AsyncClient, headers: dict[str, str], sale_id: str, key: str
) -> dict[str, Any]:
    created = await client.post(
        "/api/v1/invoices",
        headers={**headers, "Idempotency-Key": key},
        json={"sale_id": sale_id},
    )
    assert created.status_code == 201, created.text
    invoice = created.json()["invoice"]
    issued = await client.post(
        f"/api/v1/invoices/{invoice['id']}/issue",
        headers={**headers, "Idempotency-Key": f"{key}-issue"},
    )
    assert issued.status_code == 200, issued.text
    return issued.json()["invoice"]


async def _payment(
    client: AsyncClient,
    headers: dict[str, str],
    customer_id: str,
    invoice_id: str,
    amount: str,
    key: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/payments",
        headers={**headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "payment_date": date.today().isoformat(),
            "amount": amount,
            "payment_method": "cash",
            "reference_number": key.upper(),
            "allocations": [{"invoice_id": invoice_id, "allocated_amount": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["payment"]


async def test_dashboard_search_reports_and_csv_are_tenant_scoped(
    client: AsyncClient,
) -> None:
    _, headers_a = await _signup(client, "business-a")
    customer = await _customer(client, headers_a, "Alpha Retail")
    mango = await _product(
        client,
        headers_a,
        "Mango Box",
        price="10",
        threshold="5",
        sku="MANGO-SEARCH",
    )
    banana = await _product(
        client,
        headers_a,
        "Low Banana",
        price="5",
        threshold="5",
        sku="BANANA-LOW",
    )
    out_product = await _product(
        client,
        headers_a,
        "Empty Coconut",
        price="7",
        threshold="3",
        sku="COCONUT-OUT",
    )
    await _opening_stock(client, headers_a, mango["id"], "20", "insights-mango-opening")
    await _opening_stock(client, headers_a, banana["id"], "2", "insights-banana-opening")

    sale_one = await _sale(
        client, headers_a, customer["id"], mango["id"], "3", "10", "insights-sale-1"
    )
    sale_two = await _sale(
        client, headers_a, customer["id"], mango["id"], "1", "10", "insights-sale-2"
    )
    invoice = await _invoice(client, headers_a, sale_one["id"], "insights-invoice")
    payment = await _payment(
        client,
        headers_a,
        customer["id"],
        invoice["id"],
        "15",
        "insights-payment",
    )

    dashboard = await client.get("/api/v1/dashboard", headers=headers_a)
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["currency"] == "INR"
    assert body["timezone"] == "Asia/Kolkata"
    assert body["today_sales"]["value"] == "40.00"
    assert body["today_collections"]["value"] == "15.00"
    assert body["outstanding_receivables"]["value"] == "25.00"
    assert body["total_customers"]["value"] == "1"
    assert body["active_products"]["value"] == "3"
    assert body["inventory_value"]["value"] == "170.00"
    assert body["low_stock_products"]["value"] == "1"
    assert body["out_of_stock_products"]["value"] == "1"
    assert body["recent_sales"][0]["number"] == sale_two["sale_number"]
    assert body["recent_payments"][0]["number"] == payment["payment_number"]
    assert body["recent_invoices"][0]["number"] == invoice["invoice_number"]
    assert body["top_selling_products"][0]["product_name"] == "Mango Box"
    assert body["highest_outstanding_customers"][0]["customer_name"] == "Alpha Retail"

    search = await client.get("/api/v1/search", headers=headers_a, params={"q": "mango"})
    assert search.status_code == 200, search.text
    search_body = search.json()
    assert [item["title"] for item in search_body["products"]] == ["Mango Box"]
    assert [item["title"] for item in search_body["inventory"]] == ["Mango Box"]
    invoice_search = await client.get(
        "/api/v1/search", headers=headers_a, params={"q": invoice["invoice_number"]}
    )
    assert invoice_search.status_code == 200, invoice_search.text
    assert invoice_search.json()["invoices"][0]["title"] == invoice["invoice_number"]

    sales = await client.get(
        "/api/v1/reports/sales",
        headers=headers_a,
        params={"limit": 1, "sort": "oldest"},
    )
    assert sales.status_code == 200, sales.text
    assert sales.json()["items"][0]["sale_number"] == sale_one["sale_number"]
    assert sales.json()["next_cursor"]
    sales_next = await client.get(
        "/api/v1/reports/sales",
        headers=headers_a,
        params={
            "limit": 1,
            "sort": "oldest",
            "cursor": sales.json()["next_cursor"],
        },
    )
    assert sales_next.status_code == 200, sales_next.text
    assert sales_next.json()["items"][0]["sale_number"] == sale_two["sale_number"]

    payments = await client.get("/api/v1/reports/payments", headers=headers_a)
    assert payments.status_code == 200, payments.text
    assert payments.json()["items"][0]["allocated"] == "15.00"
    assert payments.json()["items"][0]["unallocated"] == "0.00"

    outstanding = await client.get("/api/v1/reports/outstanding", headers=headers_a)
    assert outstanding.status_code == 200, outstanding.text
    assert outstanding.json()["items"][0]["outstanding_balance"] == "25.00"

    inventory = await client.get(
        "/api/v1/reports/inventory",
        headers=headers_a,
        params={"sort": "stock_asc"},
    )
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["items"][0]["product"] == "Empty Coconut"
    assert {
        item["product"]: item["low_stock_status"] for item in inventory.json()["items"]
    } == {
        "Empty Coconut": "out",
        "Low Banana": "low",
        "Mango Box": "ok",
    }

    low_stock = await client.get("/api/v1/reports/low-stock", headers=headers_a)
    assert low_stock.status_code == 200, low_stock.text
    assert {item["product"] for item in low_stock.json()["items"]} == {
        "Empty Coconut",
        "Low Banana",
    }

    csv_response = await client.get("/api/v1/reports/sales.csv", headers=headers_a)
    assert csv_response.status_code == 200, csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "Sale Number,Customer,Date,Items,Subtotal,Total,Currency,Status" in csv_response.text
    assert ",INR," in csv_response.text
    assert sale_one["sale_number"] in csv_response.text

    _, headers_b = await _signup(client, "business-b")
    tenant_b_dashboard = await client.get("/api/v1/dashboard", headers=headers_b)
    assert tenant_b_dashboard.status_code == 200, tenant_b_dashboard.text
    assert tenant_b_dashboard.json()["today_sales"]["value"] == "0.00"
    tenant_b_search = await client.get(
        "/api/v1/search", headers=headers_b, params={"q": "Alpha"}
    )
    assert tenant_b_search.status_code == 200, tenant_b_search.text
    assert tenant_b_search.json()["customers"] == []
    tenant_b_csv = await client.get("/api/v1/reports/sales.csv", headers=headers_b)
    assert tenant_b_csv.status_code == 200, tenant_b_csv.text
    assert "Alpha Retail" not in tenant_b_csv.text
    assert out_product["product_code"] not in tenant_b_csv.text


async def test_insights_support_empty_business_and_actionable_filter_errors(
    client: AsyncClient,
) -> None:
    _, headers = await _signup(client, "empty")

    dashboard = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["today_sales"]["value"] == "0.00"
    assert body["recent_sales"] == []
    assert body["top_selling_products"] == []

    empty_sales = await client.get("/api/v1/reports/sales", headers=headers)
    assert empty_sales.status_code == 200, empty_sales.text
    assert empty_sales.json() == {"currency": "INR", "items": [], "next_cursor": None}

    missing_search = await client.get("/api/v1/search", headers=headers, params={"q": ""})
    assert missing_search.status_code == 422
    assert "search term" in missing_search.text

    invalid_custom_range = await client.get(
        "/api/v1/reports/sales",
        headers=headers,
        params={"period": "custom", "date_from": date.today().isoformat()},
    )
    assert invalid_custom_range.status_code == 422
    assert invalid_custom_range.json()["error"]["code"] == "REPORT_FILTER_INVALID"

    invalid_cursor = await client.get(
        "/api/v1/reports/inventory",
        headers=headers,
        params={"cursor": "not-a-valid-cursor"},
    )
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["error"]["code"] == "INVALID_REPORT_CURSOR"
