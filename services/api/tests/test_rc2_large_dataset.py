from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings


async def test_ten_thousand_plus_customers_and_products_remain_paginated_and_searchable(
    client: AsyncClient,
    test_settings: Settings,
) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Large Dataset Traders",
            "email": "large-dataset@example.com",
            "password": "secure-pass-123",
        },
    )
    assert signup.status_code == 201, signup.text
    body = signup.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    tenant_id = body["user"]["business"]["id"]
    user_id = body["user"]["id"]
    record_count = 10_001

    admin_url = test_settings.database_admin_url
    assert admin_url is not None
    engine = create_async_engine(admin_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO customers (
                        id, tenant_id, customer_code, name, phone, email,
                        archived, created_by, updated_by
                    )
                    SELECT
                        gen_random_uuid(),
                        :tenant_id,
                        'CUST-BULK-' || lpad(series.number::text, 5, '0'),
                        'Bulk Customer ' || lpad(series.number::text, 5, '0') ||
                            CASE
                                WHEN series.number = :record_count
                                THEN ' മലയാളം 😀'
                                ELSE ''
                            END,
                        CASE
                            WHEN series.number = :record_count
                            THEN '+919876543210'
                            ELSE NULL
                        END,
                        CASE
                            WHEN series.number = :record_count
                            THEN 'bulk10001@example.com'
                            ELSE NULL
                        END,
                        false,
                        :user_id,
                        :user_id
                    FROM generate_series(1, :record_count) AS series(number)
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "record_count": record_count},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO products (
                        id, tenant_id, product_code, name, sku, barcode, category,
                        description, selling_price, unit, low_stock_threshold,
                        archived, created_by, updated_by
                    )
                    SELECT
                        gen_random_uuid(),
                        :tenant_id,
                        'PROD-BULK-' || lpad(series.number::text, 5, '0'),
                        'Bulk Product ' || lpad(series.number::text, 5, '0') ||
                            CASE
                                WHEN series.number = :record_count
                                THEN ' العربية हिन्दी മലയാളം 😀'
                                ELSE ''
                            END,
                        NULL,
                        NULL,
                        'Bulk',
                        'Bulk seeded product for pagination/search verification.',
                        ((series.number % 100)::numeric + 0.99)::numeric(14, 2),
                        'kg',
                        5.000,
                        false,
                        :user_id,
                        :user_id
                    FROM generate_series(1, :record_count) AS series(number)
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "record_count": record_count},
            )
    finally:
        await engine.dispose()

    customers = await client.get("/api/v1/customers?limit=25", headers=headers)
    assert customers.status_code == 200, customers.text
    assert len(customers.json()["items"]) == 25
    assert customers.json()["page_size"] == 25
    assert customers.json()["has_more"] is True

    products = await client.get("/api/v1/products?limit=25", headers=headers)
    assert products.status_code == 200, products.text
    assert len(products.json()["items"]) == 25
    assert products.json()["page_size"] == 25
    assert products.json()["has_more"] is True

    customer_search = await client.get(
        "/api/v1/customers/search?q=bulk10001%40example.com&limit=10",
        headers=headers,
    )
    assert customer_search.status_code == 200, customer_search.text
    assert customer_search.json()["items"][0]["customer_code"] == "CUST-BULK-10001"
    assert "മലയാളം" in customer_search.json()["items"][0]["name"]

    product_search = await client.get(
        "/api/v1/products/search?q=product%2010001&limit=10",
        headers=headers,
    )
    assert product_search.status_code == 200, product_search.text
    assert product_search.json()["items"][0]["product_code"] == "PROD-BULK-10001"

    global_search = await client.get("/api/v1/search?q=10001", headers=headers)
    assert global_search.status_code == 200, global_search.text
    global_body = global_search.json()
    assert any(item["reference"] == "CUST-BULK-10001" for item in global_body["customers"])
    assert any(item["reference"] == "PROD-BULK-10001" for item in global_body["products"])

    dashboard = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    dashboard_body = dashboard.json()
    assert dashboard_body["total_customers"]["value"] == str(record_count)
    assert dashboard_body["active_products"]["value"] == str(record_count)
