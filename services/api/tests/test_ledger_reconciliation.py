from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from distributoros.core.config import Settings
from distributoros.modules.ledger.reconciliation import LedgerReconciliationService


def _admin_engine(settings: Settings) -> AsyncEngine:
    assert settings.database_admin_url is not None
    return create_async_engine(settings.database_admin_url)


async def _posted_sale(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Ledger Reconciliation",
            "email": "ledger-reconciliation@example.com",
            "password": "secure-pass-123",
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    customer = (
        await client.post(
            "/api/v1/customers", headers=headers, json={"name": "Reconcile Customer"}
        )
    ).json()["customer"]
    product = (
        await client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": "Reconcile Product",
                "selling_price": "12",
                "unit": "piece",
                "low_stock_threshold": "0",
            },
        )
    ).json()["product"]
    await client.post(
        "/api/v1/inventory/opening-stock",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"product_id": product["id"], "quantity": "10"},
    )
    sale = (
        await client.post(
            "/api/v1/sales",
            headers={**headers, "Idempotency-Key": "reconcile-sale"},
            json={
                "customer_id": customer["id"],
                "items": [
                    {"product_id": product["id"], "quantity": "2", "unit_price": "12"}
                ],
            },
        )
    ).json()["sale"]
    posted = await client.post(
        f"/api/v1/sales/{sale['id']}/post",
        headers={**headers, "Idempotency-Key": "reconcile-post"},
    )
    assert posted.status_code == 200, posted.text
    return headers, customer["id"], sale["id"]


async def test_empty_ledger_projection_is_consistent(test_settings: Settings) -> None:
    engine = _admin_engine(test_settings)
    try:
        report = await LedgerReconciliationService(engine).reconcile()
        assert report.entry_count == 0
        assert report.projection_count == 0
        assert report.is_consistent
    finally:
        await engine.dispose()


async def test_projection_rebuild_uses_immutable_ledger_history(
    client: AsyncClient, test_settings: Settings
) -> None:
    headers, customer_id, _ = await _posted_sale(client)
    engine = _admin_engine(test_settings)
    try:
        service = LedgerReconciliationService(engine)
        before = await service.reconcile()
        assert before.entry_count == 1
        assert before.is_consistent
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE customer_balance_projections
                    SET outstanding_balance = 999, total_sales = 999
                    WHERE customer_id = :customer_id
                    """
                ),
                {"customer_id": customer_id},
            )
            immutable_count = await connection.scalar(
                text("SELECT count(*) FROM customer_ledger_entries")
            )
        mismatch = await service.reconcile()
        assert not mismatch.is_consistent
        assert len(mismatch.balance_mismatches) == 1

        rebuilt = await service.rebuild()
        assert rebuilt.after.is_consistent
        async with engine.connect() as connection:
            assert await connection.scalar(
                text("SELECT count(*) FROM customer_ledger_entries")
            ) == immutable_count
    finally:
        await engine.dispose()
    summary = await client.get(
        f"/api/v1/customers/{customer_id}/financial-summary", headers=headers
    )
    assert summary.json()["outstanding_balance"] == "24.00"
    assert summary.json()["total_sales"] == "24.00"


async def test_reversal_projection_reconciles(
    client: AsyncClient, test_settings: Settings
) -> None:
    headers, customer_id, sale_id = await _posted_sale(client)
    voided = await client.post(
        f"/api/v1/sales/{sale_id}/void",
        headers={**headers, "Idempotency-Key": "reconcile-void"},
    )
    assert voided.status_code == 200, voided.text
    engine = _admin_engine(test_settings)
    try:
        report = await LedgerReconciliationService(engine).reconcile()
        assert report.entry_count == 2
        assert report.is_consistent
    finally:
        await engine.dispose()
    summary = await client.get(
        f"/api/v1/customers/{customer_id}/financial-summary", headers=headers
    )
    assert summary.json()["outstanding_balance"] == "0.00"
    assert summary.json()["total_sales"] == "0.00"
