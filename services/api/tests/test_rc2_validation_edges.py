from httpx import AsyncClient


async def test_maximum_lengths_and_multilingual_unicode_round_trip(
    client: AsyncClient,
) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "വ" * 120,
            "email": "unicode-edges@example.com",
            "password": "p" * 128,
        },
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    customer_name = "മ" * 159 + "😀"
    customer = await client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": customer_name,
            "address_line_1": "الهند · भारत · കേരളം",
            "city": "دبي",
            "notes": "नमस्ते മലയാളം مرحبا 😀" * 80,
        },
    )
    assert customer.status_code == 201, customer.text
    assert customer.json()["customer"]["name"] == customer_name
    assert customer.json()["customer"]["address_line_1"] == "الهند · भारत · കേരളം"

    product_name = "उ" * 159 + "📦"
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": product_name,
            "description": "زيت · എണ്ണ · तेल 😀" * 90,
            "selling_price": "12.50",
            "unit": "kg",
            "low_stock_threshold": "1.250",
        },
    )
    assert product.status_code == 201, product.text
    assert product.json()["product"]["name"] == product_name

    too_long_customer = await client.post(
        "/api/v1/customers", headers=headers, json={"name": "x" * 161}
    )
    too_long_product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "x" * 161,
            "selling_price": "1",
            "unit": "piece",
            "low_stock_threshold": "0",
        },
    )
    assert too_long_customer.status_code == 422
    assert too_long_product.status_code == 422
    assert too_long_customer.json()["error"]["field_errors"]["name"] == (
        "Customer name must not exceed 160 characters."
    )
    assert too_long_product.json()["error"]["field_errors"]["name"] == (
        "Product name must not exceed 160 characters."
    )


async def test_xss_like_text_is_stored_as_inert_data_and_password_limit_is_enforced(
    client: AsyncClient,
) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Validation Security",
            "email": "validation-security@example.com",
            "password": "secure-pass-123",
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    hostile = '<script>alert("x")</script> 😀'
    created = await client.post(
        "/api/v1/customers", headers=headers, json={"name": hostile}
    )
    assert created.status_code == 201
    assert created.json()["customer"]["name"] == hostile

    too_long_password = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Too Long Password",
            "email": "too-long-password@example.com",
            "password": "p" * 129,
        },
    )
    assert too_long_password.status_code == 422
    assert too_long_password.json()["error"]["field_errors"]["password"] == (
        "Password must not exceed 128 characters."
    )
