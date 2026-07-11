import asyncio
from typing import Any

from alembic import command
from alembic.config import Config
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings


async def _draft(client: AsyncClient, suffix: str) -> tuple[dict[str, Any], dict[str, str]]:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Backfill {suffix}",
            "email": f"backfill-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    customer = (
        await client.post(
            "/api/v1/customers",
            headers=headers,
            json={"name": f"Backfill Customer {suffix}"},
        )
    ).json()["customer"]
    product = (
        await client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": f"Backfill Product {suffix}",
                "selling_price": "25",
                "unit": "piece",
                "low_stock_threshold": "0",
            },
        )
    ).json()["product"]
    sale = (
        await client.post(
            "/api/v1/sales",
            headers={**headers, "Idempotency-Key": f"backfill-{suffix}"},
            json={
                "customer_id": customer["id"],
                "items": [
                    {"product_id": product["id"], "quantity": "2", "unit_price": "25"}
                ],
            },
        )
    ).json()["sale"]
    return {"sale": sale, "customer": customer}, headers


async def test_migration_backfills_posted_and_voided_phase_5a_sales(
    client: AsyncClient, test_settings: Settings
) -> None:
    posted, _ = await _draft(client, "posted")
    voided, _ = await _draft(client, "voided")
    config = Config("alembic.ini")
    downgraded = False
    try:
        await asyncio.to_thread(command.downgrade, config, "20260629_0006")
        downgraded = True
        assert test_settings.database_admin_url is not None
        engine = create_async_engine(test_settings.database_admin_url)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE sales
                    SET status = 'POSTED', post_idempotency_key = 'legacy-posted',
                        updated_at = now()
                    WHERE id = :sale_id
                    """
                ),
                {"sale_id": posted["sale"]["id"]},
            )
            await connection.execute(
                text(
                    """
                    UPDATE sales
                    SET status = 'POSTED', post_idempotency_key = 'legacy-void-post',
                        updated_at = now()
                    WHERE id = :sale_id
                    """
                ),
                {"sale_id": voided["sale"]["id"]},
            )
            await connection.execute(
                text(
                    """
                    UPDATE sales
                    SET status = 'VOID', void_idempotency_key = 'legacy-void',
                        updated_at = now()
                    WHERE id = :sale_id
                    """
                ),
                {"sale_id": voided["sale"]["id"]},
            )
        await engine.dispose()
        await asyncio.to_thread(command.upgrade, config, "head")
        downgraded = False

        engine = create_async_engine(test_settings.database_admin_url)
        async with engine.connect() as connection:
            posted_entries = (
                await connection.execute(
                    text(
                        "SELECT entry_type, debit, credit FROM customer_ledger_entries "
                        "WHERE reference_id = :sale_id ORDER BY entry_type"
                    ),
                    {"sale_id": posted["sale"]["id"]},
                )
            ).all()
            voided_entries = (
                await connection.execute(
                    text(
                        "SELECT entry_type, debit, credit FROM customer_ledger_entries "
                        "WHERE reference_id = :sale_id ORDER BY entry_type"
                    ),
                    {"sale_id": voided["sale"]["id"]},
                )
            ).all()
            posted_balance = await connection.scalar(
                text(
                    "SELECT outstanding_balance FROM customer_balance_projections "
                    "WHERE customer_id = :customer_id"
                ),
                {"customer_id": posted["customer"]["id"]},
            )
            voided_balance = await connection.scalar(
                text(
                    "SELECT outstanding_balance FROM customer_balance_projections "
                    "WHERE customer_id = :customer_id"
                ),
                {"customer_id": voided["customer"]["id"]},
            )
        await engine.dispose()
        assert [(row.entry_type, str(row.debit), str(row.credit)) for row in posted_entries] == [
            ("SALE", "50.00", "0.00")
        ]
        assert {(row.entry_type, str(row.debit), str(row.credit)) for row in voided_entries} == {
            ("SALE", "50.00", "0.00"),
            ("REVERSAL", "0.00", "50.00"),
        }
        assert str(posted_balance) == "50.00"
        assert str(voided_balance) == "0.00"
    finally:
        if downgraded:
            await asyncio.to_thread(command.upgrade, config, "head")
