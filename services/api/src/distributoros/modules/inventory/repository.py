from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.identity.models import User
from distributoros.modules.inventory.models import StockBalance, StockMovement, Warehouse
from distributoros.modules.products.models import Product


@dataclass(frozen=True)
class StockRow:
    product: Product
    warehouse: Warehouse
    available_quantity: Decimal
    updated_at: datetime | None


@dataclass(frozen=True)
class MovementRow:
    movement: StockMovement
    product: Product
    warehouse: Warehouse
    created_by_email: str


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    has_more: bool


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_product(self, tenant_id: UUID, product_id: UUID) -> Product | None:
        return cast(
            Product | None,
            await self.session.scalar(
                select(Product).where(
                    Product.tenant_id == tenant_id,
                    Product.id == product_id,
                )
            ),
        )

    async def get_warehouse(self, tenant_id: UUID, warehouse_id: UUID) -> Warehouse | None:
        return cast(
            Warehouse | None,
            await self.session.scalar(
                select(Warehouse).where(
                    Warehouse.tenant_id == tenant_id,
                    Warehouse.id == warehouse_id,
                )
            ),
        )

    async def get_default_warehouse(self, tenant_id: UUID) -> Warehouse | None:
        return cast(
            Warehouse | None,
            await self.session.scalar(
                select(Warehouse).where(
                    Warehouse.tenant_id == tenant_id,
                    Warehouse.is_default.is_(True),
                )
            ),
        )

    def add_movement(self, movement: StockMovement) -> None:
        self.session.add(movement)

    async def get_movement_by_idempotency(
        self, tenant_id: UUID, idempotency_key: str
    ) -> StockMovement | None:
        return cast(
            StockMovement | None,
            await self.session.scalar(
                select(StockMovement).where(
                    StockMovement.tenant_id == tenant_id,
                    StockMovement.idempotency_key == idempotency_key,
                )
            ),
        )

    async def apply_delta(
        self,
        *,
        tenant_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        delta: Decimal,
    ) -> tuple[Decimal, datetime] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    WITH updated AS (
                        UPDATE stock_balances
                        SET available_quantity = available_quantity + :delta,
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND product_id = :product_id
                          AND warehouse_id = :warehouse_id
                          AND available_quantity + :delta >= 0
                        RETURNING available_quantity, updated_at
                    ),
                    inserted AS (
                        INSERT INTO stock_balances (
                            tenant_id, product_id, warehouse_id,
                            available_quantity, updated_at
                        )
                        SELECT
                            :tenant_id, :product_id, :warehouse_id, :delta, now()
                        WHERE :delta >= 0
                          AND NOT EXISTS (SELECT 1 FROM updated)
                        ON CONFLICT (tenant_id, product_id, warehouse_id)
                        DO UPDATE SET
                            available_quantity = stock_balances.available_quantity
                                + EXCLUDED.available_quantity,
                            updated_at = now()
                        WHERE stock_balances.available_quantity
                            + EXCLUDED.available_quantity >= 0
                        RETURNING available_quantity, updated_at
                    )
                    SELECT available_quantity, updated_at FROM updated
                    UNION ALL
                    SELECT available_quantity, updated_at FROM inserted
                    LIMIT 1
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "delta": delta,
                },
            )
        ).one_or_none()
        if row is not None:
            return (
                cast(Decimal, row.available_quantity),
                cast(datetime, row.updated_at),
            )
        return None

    async def get_stock(
        self, *, tenant_id: UUID, product_id: UUID, warehouse_id: UUID
    ) -> StockRow | None:
        statement = (
            select(
                Product,
                Warehouse,
                func.coalesce(StockBalance.available_quantity, Decimal("0.000")),
                StockBalance.updated_at,
            )
            .select_from(Product)
            .join(
                Warehouse,
                (Warehouse.tenant_id == tenant_id) & (Warehouse.id == warehouse_id),
            )
            .outerjoin(
                StockBalance,
                (StockBalance.tenant_id == tenant_id)
                & (StockBalance.product_id == Product.id)
                & (StockBalance.warehouse_id == warehouse_id),
            )
            .where(Product.tenant_id == tenant_id, Product.id == product_id)
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return StockRow(
            product=row[0],
            warehouse=row[1],
            available_quantity=cast(Decimal, row[2]),
            updated_at=cast(datetime | None, row[3]),
        )

    async def list_stock(
        self,
        *,
        tenant_id: UUID,
        warehouse_id: UUID,
        search: str | None,
        limit: int,
        cursor_name: str | None,
        cursor_id: UUID | None,
    ) -> Page[StockRow]:
        statement = (
            select(
                Product,
                Warehouse,
                func.coalesce(StockBalance.available_quantity, Decimal("0.000")),
                StockBalance.updated_at,
            )
            .select_from(Product)
            .join(
                Warehouse,
                (Warehouse.tenant_id == tenant_id) & (Warehouse.id == warehouse_id),
            )
            .outerjoin(
                StockBalance,
                (StockBalance.tenant_id == tenant_id)
                & (StockBalance.product_id == Product.id)
                & (StockBalance.warehouse_id == warehouse_id),
            )
            .where(Product.tenant_id == tenant_id, Product.archived.is_(False))
        )
        if search:
            term = search.strip().lower()
            statement = statement.where(
                or_(
                    func.lower(Product.name).contains(term, autoescape=True),
                    func.lower(Product.product_code).contains(term, autoescape=True),
                    func.lower(Product.sku).contains(term, autoescape=True),
                    Product.barcode.contains(search.strip(), autoescape=True),
                )
            )
        normalized_name = func.lower(Product.name)
        if cursor_name is not None and cursor_id is not None:
            statement = statement.where(
                tuple_(normalized_name, Product.id) > (cursor_name, cursor_id)
            )
        statement = statement.order_by(normalized_name.asc(), Product.id.asc()).limit(limit + 1)
        rows = (await self.session.execute(statement)).all()
        items = [
            StockRow(
                product=row[0],
                warehouse=row[1],
                available_quantity=cast(Decimal, row[2]),
                updated_at=cast(datetime | None, row[3]),
            )
            for row in rows[:limit]
        ]
        return Page(items=items, has_more=len(rows) > limit)

    async def movement_row(self, tenant_id: UUID, movement_id: UUID) -> MovementRow | None:
        statement = self._movement_select().where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.id == movement_id,
        )
        row = (await self.session.execute(statement)).one_or_none()
        return self._to_movement_row(row) if row else None

    async def list_history(
        self,
        *,
        tenant_id: UUID,
        warehouse_id: UUID,
        product_id: UUID | None,
        search: str | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> Page[MovementRow]:
        statement = self._movement_select().where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.warehouse_id == warehouse_id,
        )
        if product_id:
            statement = statement.where(StockMovement.product_id == product_id)
        if search:
            term = search.strip().lower()
            statement = statement.where(
                or_(
                    func.lower(Product.name).contains(term, autoescape=True),
                    func.lower(Product.product_code).contains(term, autoescape=True),
                )
            )
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                tuple_(StockMovement.created_at, StockMovement.id) < (cursor_created_at, cursor_id)
            )
        statement = statement.order_by(
            StockMovement.created_at.desc(), StockMovement.id.desc()
        ).limit(limit + 1)
        rows = (await self.session.execute(statement)).all()
        items = [self._to_movement_row(row) for row in rows[:limit]]
        return Page(items=items, has_more=len(rows) > limit)

    @staticmethod
    def _movement_select() -> Select[tuple[StockMovement, Product, Warehouse, str]]:
        return (
            select(StockMovement, Product, Warehouse, User.email)
            .select_from(StockMovement)
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .join(User, User.id == StockMovement.created_by)
        )

    @staticmethod
    def _to_movement_row(row: object) -> MovementRow:
        values = cast(tuple[StockMovement, Product, Warehouse, str], row)
        return MovementRow(
            movement=values[0],
            product=values[1],
            warehouse=values[2],
            created_by_email=values[3],
        )
