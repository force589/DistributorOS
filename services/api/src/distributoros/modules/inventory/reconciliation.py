from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from distributoros.core.database import set_internal_maintenance_context


class BalanceIdentity(BaseModel):
    tenant_id: UUID
    warehouse_id: UUID
    product_id: UUID


class MissingProjection(BalanceIdentity):
    rebuilt_quantity: Decimal
    movement_count: int


class ExtraProjection(BalanceIdentity):
    projected_quantity: Decimal


class QuantityMismatch(BalanceIdentity):
    rebuilt_quantity: Decimal
    projected_quantity: Decimal
    difference: Decimal
    movement_count: int


class NegativeBalance(BalanceIdentity):
    source: Literal["movement_history", "projection"]
    quantity: Decimal


class InvalidReference(BaseModel):
    source: Literal["movement_history", "projection"]
    movement_id: UUID | None
    tenant_id: UUID
    warehouse_id: UUID
    product_id: UUID
    reference_id: UUID
    reason: Literal["missing_or_cross_tenant"] = "missing_or_cross_tenant"


class ReconciliationReport(BaseModel):
    generated_at: datetime
    movement_count: int
    rebuilt_balance_count: int
    projection_count: int
    missing_projections: list[MissingProjection]
    extra_projections: list[ExtraProjection]
    quantity_mismatches: list[QuantityMismatch]
    negative_balances: list[NegativeBalance]
    invalid_warehouse_references: list[InvalidReference]
    invalid_product_references: list[InvalidReference]
    discrepancy_count: int
    is_consistent: bool


class RebuildResult(BaseModel):
    rebuilt_at: datetime
    deleted_projection_count: int
    created_projection_count: int
    before: ReconciliationReport
    after: ReconciliationReport


class RebuildBlockedError(Exception):
    def __init__(self, report: ReconciliationReport) -> None:
        super().__init__(
            "Projection rebuild was blocked by invalid references or negative movement totals."
        )
        self.report = report


class ReconciliationInvariantError(Exception):
    def __init__(self, report: ReconciliationReport) -> None:
        super().__init__("Projection rebuild did not produce a consistent result.")
        self.report = report


class InventoryReconciliationService:
    """Reconcile all tenants using an administrative PostgreSQL connection."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.logger = structlog.get_logger("distributoros.inventory.reconciliation")

    async def reconcile(self) -> ReconciliationReport:
        async with self.engine.connect() as connection, connection.begin():
            await connection.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            )
            await set_internal_maintenance_context(connection)
            report = await self._report(connection)
        self.logger.info(
            "inventory_reconciliation_completed",
            movement_count=report.movement_count,
            rebuilt_balance_count=report.rebuilt_balance_count,
            projection_count=report.projection_count,
            discrepancy_count=report.discrepancy_count,
            is_consistent=report.is_consistent,
        )
        return report

    async def rebuild(self) -> RebuildResult:
        async with self.engine.connect() as connection, connection.begin():
            await connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            await set_internal_maintenance_context(connection)
            # Inventory posting writes movement history before its projection. Taking locks in
            # the same order avoids partial snapshots and prevents a concurrent post from being
            # lost while the projection table is replaced.
            await connection.execute(text("LOCK TABLE stock_movements IN SHARE MODE"))
            await connection.execute(text("LOCK TABLE stock_balances IN ACCESS EXCLUSIVE MODE"))
            before = await self._report(connection)
            invalid_movement_reference = any(
                reference.source == "movement_history"
                for reference in (
                    *before.invalid_product_references,
                    *before.invalid_warehouse_references,
                )
            )
            if invalid_movement_reference or any(
                balance.source == "movement_history" for balance in before.negative_balances
            ):
                raise RebuildBlockedError(before)

            deleted = await connection.execute(text("DELETE FROM stock_balances"))
            created = await connection.execute(
                text(
                    """
                    INSERT INTO stock_balances (
                        tenant_id,
                        product_id,
                        warehouse_id,
                        available_quantity,
                        updated_at
                    )
                    SELECT
                        tenant_id,
                        product_id,
                        warehouse_id,
                        sum(quantity),
                        now()
                    FROM stock_movements
                    GROUP BY tenant_id, product_id, warehouse_id
                    """
                )
            )
            after = await self._report(connection)
            if not after.is_consistent:
                raise ReconciliationInvariantError(after)

            result = RebuildResult(
                rebuilt_at=datetime.now(UTC),
                deleted_projection_count=max(deleted.rowcount or 0, 0),
                created_projection_count=max(created.rowcount or 0, 0),
                before=before,
                after=after,
            )
        self.logger.warning(
            "inventory_projection_rebuilt",
            deleted_projection_count=result.deleted_projection_count,
            created_projection_count=result.created_projection_count,
            prior_discrepancy_count=result.before.discrepancy_count,
        )
        return result

    async def _report(self, connection: AsyncConnection) -> ReconciliationReport:
        comparison_rows = (await connection.execute(text(_COMPARISON_SQL))).mappings().all()
        invalid_rows = (await connection.execute(text(_INVALID_REFERENCES_SQL))).mappings().all()

        summary = comparison_rows[0]
        missing: list[MissingProjection] = []
        extra: list[ExtraProjection] = []
        mismatches: list[QuantityMismatch] = []
        negative: list[NegativeBalance] = []

        for row in comparison_rows:
            if row["tenant_id"] is None:
                continue
            identity = {
                "tenant_id": cast(UUID, row["tenant_id"]),
                "warehouse_id": cast(UUID, row["warehouse_id"]),
                "product_id": cast(UUID, row["product_id"]),
            }
            rebuilt = cast(Decimal | None, row["rebuilt_quantity"])
            projected = cast(Decimal | None, row["projected_quantity"])
            movement_count = int(row["group_movement_count"] or 0)
            if rebuilt is not None and projected is None:
                missing.append(
                    MissingProjection(
                        **identity,
                        rebuilt_quantity=rebuilt,
                        movement_count=movement_count,
                    )
                )
            elif rebuilt is None and projected is not None:
                extra.append(ExtraProjection(**identity, projected_quantity=projected))
            elif rebuilt is not None and projected is not None and rebuilt != projected:
                mismatches.append(
                    QuantityMismatch(
                        **identity,
                        rebuilt_quantity=rebuilt,
                        projected_quantity=projected,
                        difference=projected - rebuilt,
                        movement_count=movement_count,
                    )
                )
            if rebuilt is not None and rebuilt < 0:
                negative.append(
                    NegativeBalance(
                        **identity,
                        source="movement_history",
                        quantity=rebuilt,
                    )
                )
            if projected is not None and projected < 0:
                negative.append(
                    NegativeBalance(
                        **identity,
                        source="projection",
                        quantity=projected,
                    )
                )

        invalid_products: list[InvalidReference] = []
        invalid_warehouses: list[InvalidReference] = []
        for row in invalid_rows:
            common: dict[str, Any] = {
                "source": row["source"],
                "movement_id": row["movement_id"],
                "tenant_id": row["tenant_id"],
                "warehouse_id": row["warehouse_id"],
                "product_id": row["product_id"],
            }
            if row["invalid_product"]:
                invalid_products.append(InvalidReference(**common, reference_id=row["product_id"]))
            if row["invalid_warehouse"]:
                invalid_warehouses.append(
                    InvalidReference(**common, reference_id=row["warehouse_id"])
                )

        discrepancy_count = (
            len(missing)
            + len(extra)
            + len(mismatches)
            + len(negative)
            + len(invalid_products)
            + len(invalid_warehouses)
        )
        return ReconciliationReport(
            generated_at=datetime.now(UTC),
            movement_count=int(summary["movement_count"]),
            rebuilt_balance_count=int(summary["rebuilt_balance_count"]),
            projection_count=int(summary["projection_count"]),
            missing_projections=missing,
            extra_projections=extra,
            quantity_mismatches=mismatches,
            negative_balances=negative,
            invalid_warehouse_references=invalid_warehouses,
            invalid_product_references=invalid_products,
            discrepancy_count=discrepancy_count,
            is_consistent=discrepancy_count == 0,
        )


_COMPARISON_SQL = """
WITH rebuilt AS MATERIALIZED (
    SELECT
        tenant_id,
        product_id,
        warehouse_id,
        sum(quantity)::numeric(20, 3) AS rebuilt_quantity,
        count(*)::bigint AS group_movement_count
    FROM stock_movements
    GROUP BY tenant_id, product_id, warehouse_id
),
summary AS (
    SELECT
        coalesce(sum(group_movement_count), 0)::bigint AS movement_count,
        count(*)::bigint AS rebuilt_balance_count,
        (SELECT count(*)::bigint FROM stock_balances) AS projection_count
    FROM rebuilt
),
comparison AS (
    SELECT
        coalesce(rebuilt.tenant_id, stock_balances.tenant_id) AS tenant_id,
        coalesce(rebuilt.product_id, stock_balances.product_id) AS product_id,
        coalesce(rebuilt.warehouse_id, stock_balances.warehouse_id) AS warehouse_id,
        rebuilt.rebuilt_quantity,
        stock_balances.available_quantity AS projected_quantity,
        rebuilt.group_movement_count
    FROM rebuilt
    FULL OUTER JOIN stock_balances
        USING (tenant_id, product_id, warehouse_id)
)
SELECT
    summary.movement_count,
    summary.rebuilt_balance_count,
    summary.projection_count,
    comparison.tenant_id,
    comparison.product_id,
    comparison.warehouse_id,
    comparison.rebuilt_quantity,
    comparison.projected_quantity,
    comparison.group_movement_count
FROM summary
LEFT JOIN comparison ON (
    comparison.rebuilt_quantity IS NULL
    OR comparison.projected_quantity IS NULL
    OR comparison.rebuilt_quantity <> comparison.projected_quantity
    OR comparison.rebuilt_quantity < 0
    OR comparison.projected_quantity < 0
)
ORDER BY comparison.tenant_id, comparison.product_id, comparison.warehouse_id
"""


_INVALID_REFERENCES_SQL = """
SELECT
    'movement_history' AS source,
    stock_movements.id AS movement_id,
    stock_movements.tenant_id,
    stock_movements.product_id,
    stock_movements.warehouse_id,
    products.id IS NULL AS invalid_product,
    warehouses.id IS NULL AS invalid_warehouse
FROM stock_movements
LEFT JOIN products
    ON products.id = stock_movements.product_id
    AND products.tenant_id = stock_movements.tenant_id
LEFT JOIN warehouses
    ON warehouses.id = stock_movements.warehouse_id
    AND warehouses.tenant_id = stock_movements.tenant_id
WHERE products.id IS NULL OR warehouses.id IS NULL
UNION ALL
SELECT
    'projection' AS source,
    NULL::uuid AS movement_id,
    stock_balances.tenant_id,
    stock_balances.product_id,
    stock_balances.warehouse_id,
    products.id IS NULL AS invalid_product,
    warehouses.id IS NULL AS invalid_warehouse
FROM stock_balances
LEFT JOIN products
    ON products.id = stock_balances.product_id
    AND products.tenant_id = stock_balances.tenant_id
LEFT JOIN warehouses
    ON warehouses.id = stock_balances.warehouse_id
    AND warehouses.tenant_id = stock_balances.tenant_id
WHERE products.id IS NULL OR warehouses.id IS NULL
ORDER BY tenant_id, movement_id NULLS LAST, product_id, warehouse_id
"""
