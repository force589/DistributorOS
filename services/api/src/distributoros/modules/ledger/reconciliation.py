# ruff: noqa: S608 -- SQL is composed only from fixed module constants.

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class CustomerBalanceIdentity(BaseModel):
    tenant_id: UUID
    customer_id: UUID


class MissingBalanceProjection(CustomerBalanceIdentity):
    rebuilt_outstanding: Decimal
    rebuilt_available_credit: Decimal
    rebuilt_total_sales: Decimal
    rebuilt_total_payments: Decimal
    rebuilt_last_sale_at: datetime | None
    rebuilt_last_payment_at: datetime | None
    entry_count: int


class ExtraBalanceProjection(CustomerBalanceIdentity):
    projected_outstanding: Decimal
    projected_available_credit: Decimal
    projected_total_sales: Decimal
    projected_total_payments: Decimal


class BalanceProjectionMismatch(CustomerBalanceIdentity):
    rebuilt_outstanding: Decimal
    projected_outstanding: Decimal
    rebuilt_available_credit: Decimal
    projected_available_credit: Decimal
    rebuilt_total_sales: Decimal
    projected_total_sales: Decimal
    rebuilt_total_payments: Decimal
    projected_total_payments: Decimal
    rebuilt_last_sale_at: datetime | None
    projected_last_sale_at: datetime | None
    rebuilt_last_payment_at: datetime | None
    projected_last_payment_at: datetime | None
    entry_count: int


class InvalidLedgerReference(BaseModel):
    source: Literal["ledger", "projection"]
    entry_id: UUID | None
    tenant_id: UUID
    customer_id: UUID
    reference_id: UUID | None
    invalid_customer: bool
    invalid_sale: bool
    invalid_payment: bool


class NegativeLedgerBalance(CustomerBalanceIdentity):
    outstanding_balance: Decimal


class LedgerReconciliationReport(BaseModel):
    generated_at: datetime
    entry_count: int
    rebuilt_balance_count: int
    projection_count: int
    missing_projections: list[MissingBalanceProjection]
    extra_projections: list[ExtraBalanceProjection]
    balance_mismatches: list[BalanceProjectionMismatch]
    negative_balances: list[NegativeLedgerBalance]
    invalid_references: list[InvalidLedgerReference]
    discrepancy_count: int
    is_consistent: bool


class LedgerRebuildResult(BaseModel):
    rebuilt_at: datetime
    deleted_projection_count: int
    created_projection_count: int
    before: LedgerReconciliationReport
    after: LedgerReconciliationReport


class LedgerRebuildBlockedError(Exception):
    def __init__(self, report: LedgerReconciliationReport) -> None:
        super().__init__("Ledger projection rebuild was blocked by invalid immutable history.")
        self.report = report


class LedgerReconciliationInvariantError(Exception):
    def __init__(self, report: LedgerReconciliationReport) -> None:
        super().__init__("Ledger projection rebuild did not produce a consistent result.")
        self.report = report


class LedgerReconciliationService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.logger = structlog.get_logger("distributoros.ledger.reconciliation")

    async def reconcile(self) -> LedgerReconciliationReport:
        async with self.engine.connect() as connection, connection.begin():
            await connection.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            )
            report = await self._report(connection)
        self.logger.info(
            "ledger_reconciliation_completed",
            entry_count=report.entry_count,
            discrepancy_count=report.discrepancy_count,
            is_consistent=report.is_consistent,
        )
        return report

    async def rebuild(self) -> LedgerRebuildResult:
        async with self.engine.connect() as connection, connection.begin():
            await connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            await connection.execute(text("LOCK TABLE customer_ledger_entries IN SHARE MODE"))
            await connection.execute(
                text("LOCK TABLE customer_balance_projections IN ACCESS EXCLUSIVE MODE")
            )
            before = await self._report(connection)
            if (
                any(reference.source == "ledger" for reference in before.invalid_references)
                or before.negative_balances
            ):
                raise LedgerRebuildBlockedError(before)
            deleted = await connection.execute(text("DELETE FROM customer_balance_projections"))
            created = await connection.execute(text(_REBUILD_SQL))
            after = await self._report(connection)
            if not after.is_consistent:
                raise LedgerReconciliationInvariantError(after)
            result = LedgerRebuildResult(
                rebuilt_at=datetime.now(UTC),
                deleted_projection_count=max(deleted.rowcount or 0, 0),
                created_projection_count=max(created.rowcount or 0, 0),
                before=before,
                after=after,
            )
        self.logger.warning(
            "ledger_projection_rebuilt",
            deleted_projection_count=result.deleted_projection_count,
            created_projection_count=result.created_projection_count,
            prior_discrepancy_count=result.before.discrepancy_count,
        )
        return result

    async def _report(self, connection: AsyncConnection) -> LedgerReconciliationReport:
        comparison_rows = (await connection.execute(text(_COMPARISON_SQL))).mappings().all()
        invalid_rows = (await connection.execute(text(_INVALID_REFERENCES_SQL))).mappings().all()
        summary = comparison_rows[0]
        missing: list[MissingBalanceProjection] = []
        extra: list[ExtraBalanceProjection] = []
        mismatches: list[BalanceProjectionMismatch] = []
        negative: list[NegativeLedgerBalance] = []
        for row in comparison_rows:
            if row["tenant_id"] is None:
                continue
            identity = {
                "tenant_id": cast(UUID, row["tenant_id"]),
                "customer_id": cast(UUID, row["customer_id"]),
            }
            rebuilt_outstanding = cast(Decimal | None, row["rebuilt_outstanding"])
            projected_outstanding = cast(Decimal | None, row["projected_outstanding"])
            if rebuilt_outstanding is not None and rebuilt_outstanding < 0:
                negative.append(
                    NegativeLedgerBalance(**identity, outstanding_balance=rebuilt_outstanding)
                )
            if rebuilt_outstanding is not None and projected_outstanding is None:
                missing.append(
                    MissingBalanceProjection(
                        **identity,
                        rebuilt_outstanding=rebuilt_outstanding,
                        rebuilt_available_credit=cast(Decimal, row["rebuilt_available_credit"]),
                        rebuilt_total_sales=cast(Decimal, row["rebuilt_total_sales"]),
                        rebuilt_total_payments=cast(Decimal, row["rebuilt_total_payments"]),
                        rebuilt_last_sale_at=cast(datetime | None, row["rebuilt_last_sale_at"]),
                        rebuilt_last_payment_at=cast(
                            datetime | None, row["rebuilt_last_payment_at"]
                        ),
                        entry_count=int(row["group_entry_count"]),
                    )
                )
            elif rebuilt_outstanding is None and projected_outstanding is not None:
                extra.append(
                    ExtraBalanceProjection(
                        **identity,
                        projected_outstanding=projected_outstanding,
                        projected_available_credit=cast(Decimal, row["projected_available_credit"]),
                        projected_total_sales=cast(Decimal, row["projected_total_sales"]),
                        projected_total_payments=cast(Decimal, row["projected_total_payments"]),
                    )
                )
            elif (
                rebuilt_outstanding is not None
                and projected_outstanding is not None
                and (
                    rebuilt_outstanding != projected_outstanding
                    or row["rebuilt_available_credit"] != row["projected_available_credit"]
                    or row["rebuilt_total_sales"] != row["projected_total_sales"]
                    or row["rebuilt_total_payments"] != row["projected_total_payments"]
                    or row["rebuilt_last_sale_at"] != row["projected_last_sale_at"]
                    or row["rebuilt_last_payment_at"] != row["projected_last_payment_at"]
                )
            ):
                mismatches.append(
                    BalanceProjectionMismatch(
                        **identity,
                        rebuilt_outstanding=rebuilt_outstanding,
                        projected_outstanding=projected_outstanding,
                        rebuilt_available_credit=cast(Decimal, row["rebuilt_available_credit"]),
                        projected_available_credit=cast(Decimal, row["projected_available_credit"]),
                        rebuilt_total_sales=cast(Decimal, row["rebuilt_total_sales"]),
                        projected_total_sales=cast(Decimal, row["projected_total_sales"]),
                        rebuilt_total_payments=cast(Decimal, row["rebuilt_total_payments"]),
                        projected_total_payments=cast(Decimal, row["projected_total_payments"]),
                        rebuilt_last_sale_at=cast(datetime | None, row["rebuilt_last_sale_at"]),
                        projected_last_sale_at=cast(datetime | None, row["projected_last_sale_at"]),
                        rebuilt_last_payment_at=cast(
                            datetime | None, row["rebuilt_last_payment_at"]
                        ),
                        projected_last_payment_at=cast(
                            datetime | None, row["projected_last_payment_at"]
                        ),
                        entry_count=int(row["group_entry_count"]),
                    )
                )
        invalid = [
            InvalidLedgerReference(**cast(dict[str, Any], dict(row))) for row in invalid_rows
        ]
        discrepancy_count = (
            len(missing) + len(extra) + len(mismatches) + len(negative) + len(invalid)
        )
        return LedgerReconciliationReport(
            generated_at=datetime.now(UTC),
            entry_count=int(summary["entry_count"]),
            rebuilt_balance_count=int(summary["rebuilt_balance_count"]),
            projection_count=int(summary["projection_count"]),
            missing_projections=missing,
            extra_projections=extra,
            balance_mismatches=mismatches,
            negative_balances=negative,
            invalid_references=invalid,
            discrepancy_count=discrepancy_count,
            is_consistent=discrepancy_count == 0,
        )


_REBUILT_SQL = """
SELECT
    tenant_id,
    customer_id,
    greatest(sum(debit - credit), 0)::numeric(18, 2) AS rebuilt_outstanding,
    greatest(sum(credit - debit), 0)::numeric(18, 2) AS rebuilt_available_credit,
    sum(
        CASE
            WHEN entry_type = 'SALE' THEN debit
            WHEN entry_type = 'REVERSAL' THEN -credit
            ELSE 0
        END
    )::numeric(18, 2)
        AS rebuilt_total_sales,
    sum(
        CASE
            WHEN entry_type = 'PAYMENT' THEN credit
            WHEN entry_type = 'PAYMENT_REVERSAL' THEN -debit
            ELSE 0
        END
    )::numeric(18, 2)
        AS rebuilt_total_payments,
    max(created_at) FILTER (WHERE entry_type = 'SALE') AS rebuilt_last_sale_at,
    max(created_at) FILTER (WHERE entry_type = 'PAYMENT') AS rebuilt_last_payment_at,
    count(*)::bigint AS group_entry_count
FROM customer_ledger_entries
GROUP BY tenant_id, customer_id
"""

_COMPARISON_SQL = f"""
WITH rebuilt AS MATERIALIZED ({_REBUILT_SQL}),
summary AS (
    SELECT
        coalesce(sum(group_entry_count), 0)::bigint AS entry_count,
        count(*)::bigint AS rebuilt_balance_count,
        (SELECT count(*)::bigint FROM customer_balance_projections) AS projection_count
    FROM rebuilt
),
comparison AS (
    SELECT
        coalesce(rebuilt.tenant_id, projection.tenant_id) AS tenant_id,
        coalesce(rebuilt.customer_id, projection.customer_id) AS customer_id,
        rebuilt.rebuilt_outstanding,
        rebuilt.rebuilt_available_credit,
        rebuilt.rebuilt_total_sales,
        rebuilt.rebuilt_total_payments,
        rebuilt.rebuilt_last_sale_at,
        rebuilt.rebuilt_last_payment_at,
        rebuilt.group_entry_count,
        projection.outstanding_balance AS projected_outstanding,
        projection.available_credit AS projected_available_credit,
        projection.total_sales AS projected_total_sales,
        projection.total_payments AS projected_total_payments,
        projection.last_sale_at AS projected_last_sale_at,
        projection.last_payment_at AS projected_last_payment_at
    FROM rebuilt
    FULL OUTER JOIN customer_balance_projections projection
        USING (tenant_id, customer_id)
)
SELECT
    summary.*,
    comparison.*
FROM summary
LEFT JOIN comparison ON (
    comparison.rebuilt_outstanding IS NULL
    OR comparison.projected_outstanding IS NULL
    OR comparison.rebuilt_outstanding <> comparison.projected_outstanding
    OR comparison.rebuilt_available_credit <> comparison.projected_available_credit
    OR comparison.rebuilt_total_sales <> comparison.projected_total_sales
    OR comparison.rebuilt_total_payments <> comparison.projected_total_payments
    OR comparison.rebuilt_last_sale_at IS DISTINCT FROM comparison.projected_last_sale_at
    OR comparison.rebuilt_last_payment_at
        IS DISTINCT FROM comparison.projected_last_payment_at
    OR comparison.rebuilt_outstanding < 0
)
ORDER BY comparison.tenant_id, comparison.customer_id
"""

_INVALID_REFERENCES_SQL = """
SELECT
    'ledger' AS source,
    entry.id AS entry_id,
    entry.tenant_id,
    entry.customer_id,
    entry.reference_id,
    customer.id IS NULL AS invalid_customer,
    (entry.reference_type = 'SALE' AND sale.id IS NULL) AS invalid_sale,
    (entry.reference_type = 'PAYMENT' AND payment.id IS NULL) AS invalid_payment
FROM customer_ledger_entries entry
LEFT JOIN customers customer
    ON customer.id = entry.customer_id AND customer.tenant_id = entry.tenant_id
LEFT JOIN sales sale
    ON sale.id = entry.reference_id
    AND sale.tenant_id = entry.tenant_id
    AND sale.customer_id = entry.customer_id
    AND entry.reference_type = 'SALE'
LEFT JOIN payments payment
    ON payment.id = entry.reference_id
    AND payment.tenant_id = entry.tenant_id
    AND payment.customer_id = entry.customer_id
    AND entry.reference_type = 'PAYMENT'
WHERE customer.id IS NULL
   OR (entry.reference_type = 'SALE' AND sale.id IS NULL)
   OR (entry.reference_type = 'PAYMENT' AND payment.id IS NULL)
UNION ALL
SELECT
    'projection' AS source,
    NULL::uuid AS entry_id,
    projection.tenant_id,
    projection.customer_id,
    NULL::uuid AS reference_id,
    customer.id IS NULL AS invalid_customer,
    false AS invalid_sale,
    false AS invalid_payment
FROM customer_balance_projections projection
LEFT JOIN customers customer
    ON customer.id = projection.customer_id
    AND customer.tenant_id = projection.tenant_id
WHERE customer.id IS NULL
ORDER BY tenant_id, customer_id, entry_id NULLS LAST
"""

_REBUILD_SQL = f"""
INSERT INTO customer_balance_projections (
    tenant_id, customer_id, outstanding_balance, available_credit,
    total_sales, total_payments, last_sale_at, last_payment_at, updated_at
)
SELECT
    tenant_id,
    customer_id,
    rebuilt_outstanding,
    rebuilt_available_credit,
    rebuilt_total_sales,
    rebuilt_total_payments,
    rebuilt_last_sale_at,
    rebuilt_last_payment_at,
    now()
FROM ({_REBUILT_SQL}) rebuilt
"""
