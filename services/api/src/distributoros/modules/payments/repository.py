from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, literal, not_, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from distributoros.modules.customers.models import Customer
from distributoros.modules.invoices.models import Invoice
from distributoros.modules.ledger.models import CustomerLedgerEntry
from distributoros.modules.payments.models import Payment, PaymentAllocation
from distributoros.modules.payments.schemas import (
    PaymentMethodFilter,
    PaymentSort,
    PaymentStatusFilter,
)
from distributoros.modules.sales.models import Sale


@dataclass(frozen=True)
class AllocationDetails:
    allocation: PaymentAllocation
    reference_type: str
    reference: str


@dataclass(frozen=True)
class PaymentDetails:
    payment: Payment
    customer_name: str
    allocated_amount: Decimal
    allocations: list[AllocationDetails]


@dataclass(frozen=True)
class PaymentListRow:
    payment: Payment
    customer_name: str
    allocated_amount: Decimal


@dataclass(frozen=True)
class PaymentPage:
    items: list[PaymentListRow]
    has_more: bool


@dataclass(frozen=True)
class AllocationTarget:
    entry: CustomerLedgerEntry
    reference: str
    already_allocated: Decimal
    reversed: bool
    invoice_id: UUID | None = None

    @property
    def remaining_amount(self) -> Decimal:
        if self.reversed:
            return Decimal("0.00")
        return self.entry.debit - self.already_allocated


@dataclass(frozen=True)
class InvoiceAllocationTarget:
    invoice: Invoice
    entry: CustomerLedgerEntry
    already_allocated: Decimal
    reversed: bool

    @property
    def reference(self) -> str:
        return self.invoice.invoice_number

    @property
    def remaining_amount(self) -> Decimal:
        if self.reversed:
            return Decimal("0.00")
        return self.invoice.grand_total - self.already_allocated


class PaymentsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_payment_number(self, tenant_id: UUID) -> str:
        number = await self.session.scalar(
            text(
                """
                INSERT INTO payment_number_counters (tenant_id, next_number)
                VALUES (:tenant_id, 2)
                ON CONFLICT (tenant_id) DO UPDATE
                SET next_number = payment_number_counters.next_number + 1
                RETURNING next_number - 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        if number is None:
            raise RuntimeError("Payment number allocation did not return a number.")
        return f"PAY-{int(number):06d}"

    def add_payment(self, payment: Payment) -> None:
        self.session.add(payment)

    def add_allocations(self, allocations: list[PaymentAllocation]) -> None:
        self.session.add_all(allocations)

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

    async def get(self, tenant_id: UUID, payment_id: UUID) -> Payment | None:
        return cast(
            Payment | None,
            await self.session.scalar(
                select(Payment).where(
                    Payment.tenant_id == tenant_id,
                    Payment.id == payment_id,
                )
            ),
        )

    async def get_for_update(self, tenant_id: UUID, payment_id: UUID) -> Payment | None:
        return cast(
            Payment | None,
            await self.session.scalar(
                select(Payment)
                .where(Payment.tenant_id == tenant_id, Payment.id == payment_id)
                .with_for_update()
            ),
        )

    async def get_by_number(self, tenant_id: UUID, payment_number: str) -> Payment | None:
        return cast(
            Payment | None,
            await self.session.scalar(
                select(Payment).where(
                    Payment.tenant_id == tenant_id,
                    Payment.payment_number == payment_number.upper(),
                )
            ),
        )

    async def get_by_create_key(self, tenant_id: UUID, key: str) -> Payment | None:
        return cast(
            Payment | None,
            await self.session.scalar(
                select(Payment).where(
                    Payment.tenant_id == tenant_id,
                    Payment.create_idempotency_key == key,
                )
            ),
        )

    async def details(self, tenant_id: UUID, payment: Payment) -> PaymentDetails:
        allocated = (
            self._effective_allocated_amount_expression(tenant_id, payment.id)
            if payment.status == "POSTED"
            else select(literal(Decimal("0.00"))).scalar_subquery()
        )
        summary = (
            await self.session.execute(
                select(Customer.name, allocated.label("allocated_amount")).where(
                    Customer.tenant_id == tenant_id,
                    Customer.id == payment.customer_id,
                )
            )
        ).one_or_none()
        if summary is None:
            raise RuntimeError("Payment customer could not be loaded.")
        allocations = await self.allocations_for_payment(tenant_id, payment.id)
        return PaymentDetails(
            payment=payment,
            customer_name=str(summary.name),
            allocated_amount=cast(Decimal, summary.allocated_amount),
            allocations=allocations,
        )

    async def allocations_for_payment(
        self, tenant_id: UUID, payment_id: UUID
    ) -> list[AllocationDetails]:
        statement = (
            select(
                PaymentAllocation,
                CustomerLedgerEntry.reference_type,
                Sale.sale_number,
                Invoice.invoice_number,
            )
            .join(
                CustomerLedgerEntry,
                CustomerLedgerEntry.id == PaymentAllocation.ledger_entry_id,
            )
            .outerjoin(
                Invoice,
                (Invoice.id == PaymentAllocation.invoice_id)
                & (Invoice.tenant_id == PaymentAllocation.tenant_id),
            )
            .outerjoin(
                Sale,
                (Sale.id == CustomerLedgerEntry.reference_id)
                & (Sale.tenant_id == PaymentAllocation.tenant_id)
                & (CustomerLedgerEntry.reference_type == "SALE"),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                PaymentAllocation.payment_id == payment_id,
            )
            .order_by(PaymentAllocation.created_at.asc(), PaymentAllocation.id.asc())
        )
        rows = (await self.session.execute(statement)).all()
        return [
            AllocationDetails(
                allocation=row[0],
                reference_type="INVOICE" if row[3] else str(row[1]),
                reference=str(row[3] or row[2] or "Ledger entry"),
            )
            for row in rows
        ]

    async def effective_allocated_amount(self, tenant_id: UUID, payment_id: UUID) -> Decimal:
        value = await self.session.scalar(
            self._effective_allocated_amount_expression(tenant_id, payment_id)
        )
        return value or Decimal("0.00")

    def _effective_allocated_amount_expression(self, tenant_id: UUID, payment_id: UUID) -> Any:
        reversal = aliased(CustomerLedgerEntry)
        is_reversed = (
            select(reversal.id)
            .where(
                reversal.tenant_id == PaymentAllocation.tenant_id,
                reversal.customer_id == CustomerLedgerEntry.customer_id,
                reversal.reference_type == CustomerLedgerEntry.reference_type,
                reversal.reference_id == CustomerLedgerEntry.reference_id,
                reversal.entry_type.in_(("REVERSAL", "PAYMENT_REVERSAL")),
            )
            .exists()
        )
        return (
            select(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
            .join(
                CustomerLedgerEntry,
                CustomerLedgerEntry.id == PaymentAllocation.ledger_entry_id,
            )
            .outerjoin(
                Invoice,
                (Invoice.id == PaymentAllocation.invoice_id)
                & (Invoice.tenant_id == PaymentAllocation.tenant_id),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                PaymentAllocation.payment_id == payment_id,
                not_(is_reversed),
                or_(PaymentAllocation.invoice_id.is_(None), Invoice.status == "ISSUED"),
            )
            .scalar_subquery()
        )

    async def allocation_targets(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        entry_ids: set[UUID],
    ) -> dict[UUID, AllocationTarget]:
        if not entry_ids:
            return {}
        allocated = (
            select(
                PaymentAllocation.ledger_entry_id.label("ledger_entry_id"),
                func.coalesce(
                    func.sum(PaymentAllocation.allocated_amount),
                    Decimal("0.00"),
                ).label("allocated_amount"),
            )
            .join(
                Payment,
                (Payment.id == PaymentAllocation.payment_id)
                & (Payment.tenant_id == PaymentAllocation.tenant_id),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                Payment.status == "POSTED",
                PaymentAllocation.ledger_entry_id.in_(entry_ids),
            )
            .group_by(PaymentAllocation.ledger_entry_id)
            .subquery()
        )
        reversal = aliased(CustomerLedgerEntry)
        is_reversed = (
            select(reversal.id)
            .where(
                reversal.tenant_id == CustomerLedgerEntry.tenant_id,
                reversal.customer_id == CustomerLedgerEntry.customer_id,
                reversal.reference_type == CustomerLedgerEntry.reference_type,
                reversal.reference_id == CustomerLedgerEntry.reference_id,
                reversal.entry_type.in_(("REVERSAL", "PAYMENT_REVERSAL")),
            )
            .exists()
        )
        statement = (
            select(
                CustomerLedgerEntry,
                Sale.sale_number,
                func.coalesce(allocated.c.allocated_amount, Decimal("0.00")),
                is_reversed,
            )
            .outerjoin(allocated, allocated.c.ledger_entry_id == CustomerLedgerEntry.id)
            .outerjoin(
                Sale,
                (Sale.id == CustomerLedgerEntry.reference_id)
                & (Sale.tenant_id == tenant_id)
                & (CustomerLedgerEntry.reference_type == "SALE"),
            )
            .where(
                CustomerLedgerEntry.tenant_id == tenant_id,
                CustomerLedgerEntry.customer_id == customer_id,
                CustomerLedgerEntry.id.in_(entry_ids),
                CustomerLedgerEntry.debit > 0,
                CustomerLedgerEntry.credit == 0,
            )
            .order_by(CustomerLedgerEntry.id.asc())
        )
        rows = (await self.session.execute(statement)).all()
        return {
            row[0].id: AllocationTarget(
                entry=row[0],
                reference=str(row[1] or "Ledger entry"),
                already_allocated=cast(Decimal, row[2]),
                reversed=bool(row[-1]),
            )
            for row in rows
        }

    async def invoice_allocation_targets(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        invoice_ids: set[UUID],
    ) -> dict[UUID, InvoiceAllocationTarget]:
        if not invoice_ids:
            return {}
        allocated = (
            select(
                PaymentAllocation.invoice_id.label("invoice_id"),
                func.coalesce(
                    func.sum(PaymentAllocation.allocated_amount),
                    Decimal("0.00"),
                ).label("allocated_amount"),
            )
            .join(
                Payment,
                (Payment.id == PaymentAllocation.payment_id)
                & (Payment.tenant_id == PaymentAllocation.tenant_id),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                Payment.status == "POSTED",
                PaymentAllocation.invoice_id.in_(invoice_ids),
            )
            .group_by(PaymentAllocation.invoice_id)
            .subquery()
        )
        reversal = aliased(CustomerLedgerEntry)
        is_reversed = (
            select(reversal.id)
            .where(
                reversal.tenant_id == Invoice.tenant_id,
                reversal.customer_id == Invoice.customer_id,
                reversal.reference_type == "SALE",
                reversal.reference_id == Invoice.sale_id,
                reversal.entry_type == "REVERSAL",
            )
            .exists()
        )
        statement = (
            select(
                Invoice,
                CustomerLedgerEntry,
                func.coalesce(allocated.c.allocated_amount, Decimal("0.00")),
                is_reversed,
            )
            .join(
                CustomerLedgerEntry,
                (CustomerLedgerEntry.id == Invoice.ledger_entry_id)
                & (CustomerLedgerEntry.tenant_id == Invoice.tenant_id),
            )
            .outerjoin(allocated, allocated.c.invoice_id == Invoice.id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.customer_id == customer_id,
                Invoice.id.in_(invoice_ids),
                Invoice.status == "ISSUED",
            )
            .order_by(Invoice.id.asc())
        )
        rows = (await self.session.execute(statement)).all()
        return {
            row[0].id: InvoiceAllocationTarget(
                invoice=row[0],
                entry=row[1],
                already_allocated=cast(Decimal, row[2]),
                reversed=bool(row[3]),
            )
            for row in rows
        }

    async def list_payments(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID | None,
        payment_status: PaymentStatusFilter,
        payment_method: PaymentMethodFilter,
        payment_sort: PaymentSort,
        search: str | None,
        payment_date: date | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> PaymentPage:
        reversal = aliased(CustomerLedgerEntry)
        is_reversed = (
            select(reversal.id)
            .where(
                reversal.tenant_id == PaymentAllocation.tenant_id,
                reversal.customer_id == CustomerLedgerEntry.customer_id,
                reversal.reference_type == CustomerLedgerEntry.reference_type,
                reversal.reference_id == CustomerLedgerEntry.reference_id,
                reversal.entry_type.in_(("REVERSAL", "PAYMENT_REVERSAL")),
            )
            .exists()
        )
        allocated_amount = (
            select(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
            .join(
                CustomerLedgerEntry,
                CustomerLedgerEntry.id == PaymentAllocation.ledger_entry_id,
            )
            .outerjoin(
                Invoice,
                (Invoice.id == PaymentAllocation.invoice_id)
                & (Invoice.tenant_id == PaymentAllocation.tenant_id),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                PaymentAllocation.payment_id == Payment.id,
                not_(is_reversed),
                or_(PaymentAllocation.invoice_id.is_(None), Invoice.status == "ISSUED"),
            )
            .correlate(Payment)
            .scalar_subquery()
        )
        statement = (
            select(Payment, Customer.name, allocated_amount)
            .join(
                Customer,
                (Customer.id == Payment.customer_id) & (Customer.tenant_id == tenant_id),
            )
            .where(Payment.tenant_id == tenant_id)
        )
        if customer_id is not None:
            statement = statement.where(Payment.customer_id == customer_id)
        if payment_status != "all":
            statement = statement.where(Payment.status == payment_status.upper())
        if payment_method != "all":
            statement = statement.where(Payment.payment_method == payment_method)
        if search:
            term = search.strip().lower()
            statement = statement.where(
                or_(
                    func.lower(Payment.payment_number).contains(term, autoescape=True),
                    func.lower(Payment.reference_number).contains(term, autoescape=True),
                    func.lower(Payment.payment_method).contains(term, autoescape=True),
                    func.lower(Customer.name).contains(term, autoescape=True),
                    func.lower(Customer.customer_code).contains(term, autoescape=True),
                )
            )
        if payment_date is not None:
            statement = statement.where(Payment.payment_date == payment_date)
        if cursor_created_at is not None and cursor_id is not None:
            comparison = tuple_(Payment.created_at, Payment.id)
            statement = statement.where(
                comparison < (cursor_created_at, cursor_id)
                if payment_sort == "newest"
                else comparison > (cursor_created_at, cursor_id)
            )
        statement = (
            statement.order_by(Payment.created_at.desc(), Payment.id.desc())
            if payment_sort == "newest"
            else statement.order_by(Payment.created_at.asc(), Payment.id.asc())
        ).limit(limit + 1)
        rows = (await self.session.execute(statement)).all()
        return PaymentPage(
            items=[
                PaymentListRow(
                    payment=row[0],
                    customer_name=str(row[1]),
                    allocated_amount=(
                        cast(Decimal, row[2]) if row[0].status == "POSTED" else Decimal("0.00")
                    ),
                )
                for row in rows[:limit]
            ],
            has_more=len(rows) > limit,
        )
