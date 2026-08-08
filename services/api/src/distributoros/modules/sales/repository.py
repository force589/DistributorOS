from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.customers.models import Customer
from distributoros.modules.inventory.models import StockBalance, StockMovement
from distributoros.modules.products.models import Product
from distributoros.modules.sales.models import Sale, SaleItem
from distributoros.modules.sales.schemas import SaleSort, SaleStatusFilter


@dataclass(frozen=True)
class SaleDetails:
    sale: Sale
    customer_name: str
    items: list[SaleItem]


@dataclass(frozen=True)
class SaleListRow:
    sale: Sale
    customer_name: str
    item_count: int


@dataclass(frozen=True)
class SalePage:
    items: list[SaleListRow]
    has_more: bool


class SalesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_sale_number(self, tenant_id: UUID) -> str:
        number = await self.session.scalar(
            text(
                """
                INSERT INTO sale_code_counters (tenant_id, next_number)
                VALUES (:tenant_id, 2)
                ON CONFLICT (tenant_id) DO UPDATE
                SET next_number = sale_code_counters.next_number + 1
                RETURNING next_number - 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        if number is None:
            raise RuntimeError("Sale number allocation did not return a number.")
        return f"SALE-{int(number):06d}"

    async def has_issued_invoice(self, tenant_id: UUID, sale_id: UUID) -> bool:
        value = await self.session.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM invoices
                    WHERE tenant_id = :tenant_id
                      AND sale_id = :sale_id
                      AND status = 'ISSUED'
                )
                """
            ),
            {"tenant_id": tenant_id, "sale_id": sale_id},
        )
        return bool(value)

    def add_sale(self, sale: Sale) -> None:
        self.session.add(sale)

    def add_items(self, items: list[SaleItem]) -> None:
        self.session.add_all(items)

    async def get(self, tenant_id: UUID, sale_id: UUID) -> Sale | None:
        return cast(
            Sale | None,
            await self.session.scalar(
                select(Sale).where(Sale.tenant_id == tenant_id, Sale.id == sale_id)
            ),
        )

    async def get_for_update(self, tenant_id: UUID, sale_id: UUID) -> Sale | None:
        return cast(
            Sale | None,
            await self.session.scalar(
                select(Sale)
                .where(Sale.tenant_id == tenant_id, Sale.id == sale_id)
                .with_for_update()
            ),
        )

    async def get_by_number(self, tenant_id: UUID, sale_number: str) -> Sale | None:
        return cast(
            Sale | None,
            await self.session.scalar(
                select(Sale).where(
                    Sale.tenant_id == tenant_id,
                    Sale.sale_number == sale_number.upper(),
                )
            ),
        )

    async def get_by_create_key(self, tenant_id: UUID, key: str) -> Sale | None:
        return cast(
            Sale | None,
            await self.session.scalar(
                select(Sale).where(
                    Sale.tenant_id == tenant_id,
                    Sale.create_idempotency_key == key,
                )
            ),
        )

    async def get_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer | None:
        return cast(
            Customer | None,
            await self.session.scalar(
                select(Customer).where(
                    Customer.tenant_id == tenant_id,
                    Customer.id == customer_id,
                )
            ),
        )

    async def get_products(self, tenant_id: UUID, product_ids: set[UUID]) -> list[Product]:
        if not product_ids:
            return []
        return list(
            (
                await self.session.scalars(
                    select(Product).where(
                        Product.tenant_id == tenant_id,
                        Product.id.in_(product_ids),
                    )
                )
            ).all()
        )

    async def get_items(self, sale_id: UUID) -> list[SaleItem]:
        return list(
            (
                await self.session.scalars(
                    select(SaleItem)
                    .where(SaleItem.sale_id == sale_id)
                    .order_by(SaleItem.line_number.asc())
                )
            ).all()
        )

    async def replace_items(self, sale_id: UUID, items: list[SaleItem]) -> None:
        await self.session.execute(delete(SaleItem).where(SaleItem.sale_id == sale_id))
        self.add_items(items)

    async def details(self, tenant_id: UUID, sale: Sale) -> SaleDetails:
        rows = (
            await self.session.execute(
                select(Customer.name, SaleItem)
                .select_from(Customer)
                .outerjoin(SaleItem, SaleItem.sale_id == sale.id)
                .where(
                    Customer.tenant_id == tenant_id,
                    Customer.id == sale.customer_id,
                )
                .order_by(SaleItem.line_number.asc().nulls_last())
            )
        ).all()
        if not rows:
            raise RuntimeError("Sale customer could not be loaded.")
        return SaleDetails(
            sale=sale,
            customer_name=str(rows[0][0]),
            items=[row[1] for row in rows if row[1] is not None],
        )

    async def list_sales(
        self,
        *,
        tenant_id: UUID,
        sale_status: SaleStatusFilter,
        sale_sort: SaleSort,
        search: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> SalePage:
        item_count = (
            select(func.count(SaleItem.id))
            .where(SaleItem.sale_id == Sale.id)
            .correlate(Sale)
            .scalar_subquery()
        )
        statement = (
            select(Sale, Customer.name, item_count)
            .join(
                Customer,
                (Customer.id == Sale.customer_id) & (Customer.tenant_id == tenant_id),
            )
            .where(Sale.tenant_id == tenant_id)
        )
        if sale_status != "all":
            statement = statement.where(Sale.status == sale_status.upper())
        if search:
            term = search.strip().lower()
            statement = statement.where(
                or_(
                    func.lower(Sale.sale_number).contains(term, autoescape=True),
                    func.lower(Customer.name).contains(term, autoescape=True),
                    func.lower(Customer.customer_code).contains(term, autoescape=True),
                )
            )
        if date_from:
            statement = statement.where(Sale.created_at >= date_from)
        if date_to:
            statement = statement.where(Sale.created_at < date_to)
        if cursor_created_at is not None and cursor_id is not None:
            comparison = tuple_(Sale.created_at, Sale.id)
            statement = statement.where(
                comparison < (cursor_created_at, cursor_id)
                if sale_sort == "newest"
                else comparison > (cursor_created_at, cursor_id)
            )
        statement = (
            statement.order_by(Sale.created_at.desc(), Sale.id.desc())
            if sale_sort == "newest"
            else statement.order_by(Sale.created_at.asc(), Sale.id.asc())
        ).limit(limit + 1)
        rows = (await self.session.execute(statement)).all()
        return SalePage(
            items=[
                SaleListRow(sale=row[0], customer_name=str(row[1]), item_count=int(row[2]))
                for row in rows[:limit]
            ],
            has_more=len(rows) > limit,
        )

    async def sale_movements(self, tenant_id: UUID, sale_id: UUID) -> list[StockMovement]:
        return list(
            (
                await self.session.scalars(
                    select(StockMovement)
                    .where(
                        StockMovement.tenant_id == tenant_id,
                        StockMovement.reference_type == "SALE",
                        StockMovement.reference_id == sale_id,
                        StockMovement.movement_type == "SALE",
                    )
                    .order_by(StockMovement.product_id.asc(), StockMovement.id.asc())
                )
            ).all()
        )

    async def missing_stock_projections(
        self,
        tenant_id: UUID,
        keys: set[tuple[UUID, UUID]],
    ) -> set[tuple[UUID, UUID]]:
        if not keys:
            return set()
        rows = (
            await self.session.execute(
                select(StockBalance.product_id, StockBalance.warehouse_id).where(
                    StockBalance.tenant_id == tenant_id,
                    tuple_(StockBalance.product_id, StockBalance.warehouse_id).in_(keys),
                )
            )
        ).tuples()
        return keys - set(rows)
