from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import case, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.customers.models import Customer
from distributoros.modules.ledger.models import (
    CustomerBalanceProjection,
    CustomerLedgerEntry,
)
from distributoros.modules.ledger.schemas import LedgerEntryTypeFilter
from distributoros.modules.payments.models import Payment
from distributoros.modules.sales.models import Sale


@dataclass(frozen=True)
class LedgerListRow:
    id: UUID
    entry_type: str
    reference_type: str
    reference_id: UUID
    reference: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal
    remarks: str | None
    created_at: datetime


@dataclass(frozen=True)
class LedgerPage:
    items: list[LedgerListRow]
    has_more: bool


class LedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add_entry(self, entry: CustomerLedgerEntry) -> None:
        self.session.add(entry)

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

    async def entries_for_sale(self, tenant_id: UUID, sale_id: UUID) -> list[CustomerLedgerEntry]:
        return list(
            (
                await self.session.scalars(
                    select(CustomerLedgerEntry)
                    .where(
                        CustomerLedgerEntry.tenant_id == tenant_id,
                        CustomerLedgerEntry.reference_type == "SALE",
                        CustomerLedgerEntry.reference_id == sale_id,
                    )
                    .order_by(
                        CustomerLedgerEntry.created_at.asc(),
                        CustomerLedgerEntry.id.asc(),
                    )
                )
            ).all()
        )

    async def entries_for_payment(
        self, tenant_id: UUID, payment_id: UUID
    ) -> list[CustomerLedgerEntry]:
        return list(
            (
                await self.session.scalars(
                    select(CustomerLedgerEntry)
                    .where(
                        CustomerLedgerEntry.tenant_id == tenant_id,
                        CustomerLedgerEntry.reference_type == "PAYMENT",
                        CustomerLedgerEntry.reference_id == payment_id,
                    )
                    .order_by(
                        CustomerLedgerEntry.created_at.asc(),
                        CustomerLedgerEntry.id.asc(),
                    )
                )
            ).all()
        )

    async def get_projection(
        self, tenant_id: UUID, customer_id: UUID, *, for_update: bool = False
    ) -> CustomerBalanceProjection | None:
        statement = select(CustomerBalanceProjection).where(
            CustomerBalanceProjection.tenant_id == tenant_id,
            CustomerBalanceProjection.customer_id == customer_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(CustomerBalanceProjection | None, await self.session.scalar(statement))

    async def has_customer_entries(self, tenant_id: UUID, customer_id: UUID) -> bool:
        entry_id = await self.session.scalar(
            select(CustomerLedgerEntry.id)
            .where(
                CustomerLedgerEntry.tenant_id == tenant_id,
                CustomerLedgerEntry.customer_id == customer_id,
            )
            .limit(1)
        )
        return entry_id is not None

    async def apply_sale_projection(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        sale_at: datetime,
    ) -> None:
        updated = await self._apply_projection_delta(
            tenant_id=tenant_id,
            customer_id=customer_id,
            debit=amount,
            credit=Decimal("0.00"),
            total_sales_delta=amount,
            total_payments_delta=Decimal("0.00"),
            last_sale_at=sale_at,
            last_payment_at=None,
        )
        if not updated:
            raise RuntimeError("Sale projection update did not update a row.")

    async def apply_reversal_projection(
        self, *, tenant_id: UUID, customer_id: UUID, amount: Decimal
    ) -> bool:
        return await self._apply_projection_delta(
            tenant_id=tenant_id,
            customer_id=customer_id,
            debit=Decimal("0.00"),
            credit=amount,
            total_sales_delta=-amount,
            total_payments_delta=Decimal("0.00"),
            last_sale_at=None,
            last_payment_at=None,
        )

    async def apply_payment_projection(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        payment_at: datetime,
    ) -> bool:
        return await self._apply_projection_delta(
            tenant_id=tenant_id,
            customer_id=customer_id,
            debit=Decimal("0.00"),
            credit=amount,
            total_sales_delta=Decimal("0.00"),
            total_payments_delta=amount,
            last_sale_at=None,
            last_payment_at=payment_at,
        )

    async def apply_payment_reversal_projection(
        self, *, tenant_id: UUID, customer_id: UUID, amount: Decimal
    ) -> bool:
        return await self._apply_projection_delta(
            tenant_id=tenant_id,
            customer_id=customer_id,
            debit=amount,
            credit=Decimal("0.00"),
            total_sales_delta=Decimal("0.00"),
            total_payments_delta=-amount,
            last_sale_at=None,
            last_payment_at=None,
        )

    async def _apply_projection_delta(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        debit: Decimal,
        credit: Decimal,
        total_sales_delta: Decimal,
        total_payments_delta: Decimal,
        last_sale_at: datetime | None,
        last_payment_at: datetime | None,
    ) -> bool:
        if total_sales_delta < 0 or total_payments_delta < 0:
            row = (
                await self.session.execute(
                    text(
                        """
                        UPDATE customer_balance_projections
                        SET outstanding_balance = greatest(
                                outstanding_balance - available_credit
                                + CAST(:debit AS numeric) - CAST(:credit AS numeric),
                                0::numeric
                            ),
                            available_credit = greatest(
                                available_credit - outstanding_balance
                                + CAST(:credit AS numeric) - CAST(:debit AS numeric),
                                0::numeric
                            ),
                            total_sales = total_sales + :total_sales_delta,
                            total_payments = total_payments + :total_payments_delta,
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND customer_id = :customer_id
                          AND total_sales + :total_sales_delta >= 0
                          AND total_payments + :total_payments_delta >= 0
                        RETURNING customer_id
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "customer_id": customer_id,
                        "debit": debit,
                        "credit": credit,
                        "total_sales_delta": total_sales_delta,
                        "total_payments_delta": total_payments_delta,
                    },
                )
            ).one_or_none()
            return row is not None
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO customer_balance_projections (
                        tenant_id, customer_id, outstanding_balance, available_credit,
                        total_sales, total_payments, last_sale_at, last_payment_at, updated_at
                    )
                    VALUES (
                        :tenant_id,
                        :customer_id,
                        greatest(
                            CAST(:debit AS numeric) - CAST(:credit AS numeric),
                            0::numeric
                        ),
                        greatest(
                            CAST(:credit AS numeric) - CAST(:debit AS numeric),
                            0::numeric
                        ),
                        :total_sales_delta,
                        :total_payments_delta,
                        :last_sale_at,
                        :last_payment_at,
                        now()
                    )
                    ON CONFLICT (tenant_id, customer_id)
                    DO UPDATE SET
                        outstanding_balance = greatest(
                            customer_balance_projections.outstanding_balance
                            - customer_balance_projections.available_credit
                            + CAST(:debit AS numeric) - CAST(:credit AS numeric),
                            0::numeric
                        ),
                        available_credit = greatest(
                            customer_balance_projections.available_credit
                            - customer_balance_projections.outstanding_balance
                            + CAST(:credit AS numeric) - CAST(:debit AS numeric),
                            0::numeric
                        ),
                        total_sales =
                            customer_balance_projections.total_sales + :total_sales_delta,
                        total_payments =
                            customer_balance_projections.total_payments
                            + :total_payments_delta,
                        last_sale_at = CASE
                            WHEN :last_sale_at IS NULL
                            THEN customer_balance_projections.last_sale_at
                            ELSE greatest(
                                coalesce(
                                    customer_balance_projections.last_sale_at,
                                    :last_sale_at
                                ),
                                :last_sale_at
                            )
                        END,
                        last_payment_at = CASE
                            WHEN :last_payment_at IS NULL
                            THEN customer_balance_projections.last_payment_at
                            ELSE greatest(
                                coalesce(
                                    customer_balance_projections.last_payment_at,
                                    :last_payment_at
                                ),
                                :last_payment_at
                            )
                        END,
                        updated_at = now()
                    WHERE customer_balance_projections.total_sales + :total_sales_delta >= 0
                      AND customer_balance_projections.total_payments
                          + :total_payments_delta >= 0
                    RETURNING customer_id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "customer_id": customer_id,
                    "debit": debit,
                    "credit": credit,
                    "total_sales_delta": total_sales_delta,
                    "total_payments_delta": total_payments_delta,
                    "last_sale_at": last_sale_at,
                    "last_payment_at": last_payment_at,
                },
            )
        ).one_or_none()
        return row is not None

    async def list_entries(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        entry_type: LedgerEntryTypeFilter,
        reference: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> LedgerPage:
        running = (
            select(
                CustomerLedgerEntry.id.label("id"),
                CustomerLedgerEntry.tenant_id.label("tenant_id"),
                CustomerLedgerEntry.customer_id.label("customer_id"),
                CustomerLedgerEntry.entry_type.label("entry_type"),
                CustomerLedgerEntry.reference_type.label("reference_type"),
                CustomerLedgerEntry.reference_id.label("reference_id"),
                CustomerLedgerEntry.debit.label("debit"),
                CustomerLedgerEntry.credit.label("credit"),
                CustomerLedgerEntry.remarks.label("remarks"),
                CustomerLedgerEntry.created_at.label("created_at"),
                func.sum(CustomerLedgerEntry.debit - CustomerLedgerEntry.credit)
                .over(
                    order_by=(
                        CustomerLedgerEntry.created_at.asc(),
                        CustomerLedgerEntry.id.asc(),
                    ),
                    rows=(None, 0),
                )
                .label("running_balance"),
            )
            .where(
                CustomerLedgerEntry.tenant_id == tenant_id,
                CustomerLedgerEntry.customer_id == customer_id,
            )
            .subquery()
        )
        reference_value = case(
            (running.c.reference_type == "SALE", Sale.sale_number),
            (running.c.reference_type == "PAYMENT", Payment.payment_number),
            else_="Ledger entry",
        ).label("reference")
        statement = (
            select(running, reference_value)
            .outerjoin(
                Sale,
                (Sale.id == running.c.reference_id) & (Sale.tenant_id == running.c.tenant_id),
            )
            .outerjoin(
                Payment,
                (Payment.id == running.c.reference_id) & (Payment.tenant_id == running.c.tenant_id),
            )
            .where(running.c.tenant_id == tenant_id)
        )
        if entry_type != "all":
            statement = statement.where(running.c.entry_type == entry_type.upper())
        if reference:
            statement = statement.where(
                or_(
                    func.lower(Sale.sale_number).contains(
                        reference.strip().lower(), autoescape=True
                    ),
                    func.lower(Payment.payment_number).contains(
                        reference.strip().lower(), autoescape=True
                    ),
                )
            )
        if date_from is not None:
            statement = statement.where(running.c.created_at >= date_from)
        if date_to is not None:
            statement = statement.where(running.c.created_at < date_to)
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                tuple_(running.c.created_at, running.c.id) < (cursor_created_at, cursor_id)
            )
        statement = statement.order_by(running.c.created_at.desc(), running.c.id.desc()).limit(
            limit + 1
        )
        rows = (await self.session.execute(statement)).mappings().all()
        return LedgerPage(
            items=[
                LedgerListRow(
                    id=cast(UUID, row["id"]),
                    entry_type=str(row["entry_type"]),
                    reference_type=str(row["reference_type"]),
                    reference_id=cast(UUID, row["reference_id"]),
                    reference=str(row["reference"]),
                    debit=cast(Decimal, row["debit"]),
                    credit=cast(Decimal, row["credit"]),
                    running_balance=cast(Decimal, row["running_balance"]),
                    remarks=cast(str | None, row["remarks"]),
                    created_at=cast(datetime, row["created_at"]),
                )
                for row in rows[:limit]
            ],
            has_more=len(rows) > limit,
        )
