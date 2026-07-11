from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, not_, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from distributoros.modules.customers.models import Customer
from distributoros.modules.invoices.models import Invoice, InvoiceItem
from distributoros.modules.invoices.schemas import InvoiceSort, InvoiceStatusFilter
from distributoros.modules.ledger.models import CustomerLedgerEntry
from distributoros.modules.payments.models import Payment, PaymentAllocation
from distributoros.modules.sales.models import Sale, SaleItem
from distributoros.modules.tenancy.models import Business


@dataclass(frozen=True)
class SaleInvoiceSource:
    sale: Sale
    customer: Customer
    ledger_entry: CustomerLedgerEntry
    items: list[SaleItem]


@dataclass(frozen=True)
class InvoiceDetails:
    invoice: Invoice
    business_name: str
    allocated_amount: Decimal
    items: list[InvoiceItem]

    @property
    def outstanding_amount(self) -> Decimal:
        if self.invoice.status == "VOID":
            return Decimal("0.00")
        return max(self.invoice.grand_total - self.allocated_amount, Decimal("0.00"))


@dataclass(frozen=True)
class InvoiceListRow:
    invoice: Invoice
    allocated_amount: Decimal

    @property
    def outstanding_amount(self) -> Decimal:
        if self.invoice.status == "VOID":
            return Decimal("0.00")
        return max(self.invoice.grand_total - self.allocated_amount, Decimal("0.00"))


@dataclass(frozen=True)
class InvoicePage:
    items: list[InvoiceListRow]
    has_more: bool


@dataclass(frozen=True)
class PaymentCreditRow:
    payment: Payment
    allocated_amount: Decimal

    @property
    def remaining_amount(self) -> Decimal:
        return max(self.payment.amount - self.allocated_amount, Decimal("0.00"))


class InvoicesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_invoice_number(self, tenant_id: UUID) -> str:
        number = await self.session.scalar(
            text(
                """
                INSERT INTO invoice_number_counters (tenant_id, next_number)
                VALUES (:tenant_id, 2)
                ON CONFLICT (tenant_id) DO UPDATE
                SET next_number = invoice_number_counters.next_number + 1
                RETURNING next_number - 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        if number is None:
            raise RuntimeError("Invoice number allocation did not return a number.")
        return f"INV-{int(number):06d}"

    def add_invoice(self, invoice: Invoice) -> None:
        self.session.add(invoice)

    def add_items(self, items: list[InvoiceItem]) -> None:
        self.session.add_all(items)

    def add_allocations(self, allocations: list[PaymentAllocation]) -> None:
        self.session.add_all(allocations)

    async def get_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer | None:
        return cast(
            Customer | None,
            await self.session.scalar(
                select(Customer).where(Customer.tenant_id == tenant_id, Customer.id == customer_id)
            ),
        )

    async def source_for_sale(
        self, tenant_id: UUID, sale_id: UUID, *, for_update: bool = False
    ) -> SaleInvoiceSource | None:
        sale_statement = select(Sale).where(Sale.tenant_id == tenant_id, Sale.id == sale_id)
        if for_update:
            sale_statement = sale_statement.with_for_update()
        sale = cast(Sale | None, await self.session.scalar(sale_statement))
        if sale is None:
            return None
        customer = cast(
            Customer | None,
            await self.session.scalar(
                select(Customer).where(
                    Customer.tenant_id == tenant_id,
                    Customer.id == sale.customer_id,
                )
            ),
        )
        ledger_entry = cast(
            CustomerLedgerEntry | None,
            await self.session.scalar(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.tenant_id == tenant_id,
                    CustomerLedgerEntry.customer_id == sale.customer_id,
                    CustomerLedgerEntry.reference_type == "SALE",
                    CustomerLedgerEntry.reference_id == sale.id,
                    CustomerLedgerEntry.entry_type == "SALE",
                )
            ),
        )
        items = list(
            (
                await self.session.scalars(
                    select(SaleItem)
                    .where(SaleItem.sale_id == sale.id)
                    .order_by(SaleItem.line_number.asc())
                )
            ).all()
        )
        if customer is None or ledger_entry is None:
            return None
        return SaleInvoiceSource(
            sale=sale,
            customer=customer,
            ledger_entry=ledger_entry,
            items=items,
        )

    async def get_by_sale(self, tenant_id: UUID, sale_id: UUID) -> Invoice | None:
        return cast(
            Invoice | None,
            await self.session.scalar(
                select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.sale_id == sale_id)
            ),
        )

    async def get_by_create_key(self, tenant_id: UUID, key: str) -> Invoice | None:
        return cast(
            Invoice | None,
            await self.session.scalar(
                select(Invoice).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.create_idempotency_key == key,
                )
            ),
        )

    async def get(self, tenant_id: UUID, invoice_id: UUID) -> Invoice | None:
        return cast(
            Invoice | None,
            await self.session.scalar(
                select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
            ),
        )

    async def get_for_update(self, tenant_id: UUID, invoice_id: UUID) -> Invoice | None:
        return cast(
            Invoice | None,
            await self.session.scalar(
                select(Invoice)
                .where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
                .with_for_update()
            ),
        )

    async def get_by_number(self, tenant_id: UUID, invoice_number: str) -> Invoice | None:
        return cast(
            Invoice | None,
            await self.session.scalar(
                select(Invoice).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.invoice_number == invoice_number.upper(),
                )
            ),
        )

    async def business_name(self, tenant_id: UUID) -> str:
        value = await self.session.scalar(
            select(Business.business_name).where(Business.id == tenant_id)
        )
        if value is None:
            raise RuntimeError("Invoice business could not be loaded.")
        return str(value)

    async def invoice_items(self, tenant_id: UUID, invoice_id: UUID) -> list[InvoiceItem]:
        return list(
            (
                await self.session.scalars(
                    select(InvoiceItem)
                    .where(
                        InvoiceItem.tenant_id == tenant_id,
                        InvoiceItem.invoice_id == invoice_id,
                    )
                    .order_by(InvoiceItem.line_number.asc())
                )
            ).all()
        )

    async def allocated_amount(self, tenant_id: UUID, invoice_id: UUID) -> Decimal:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
            .join(
                Payment,
                (Payment.id == PaymentAllocation.payment_id)
                & (Payment.tenant_id == PaymentAllocation.tenant_id),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                PaymentAllocation.invoice_id == invoice_id,
                Payment.status == "POSTED",
            )
        )
        return value or Decimal("0.00")

    async def details(self, tenant_id: UUID, invoice: Invoice) -> InvoiceDetails:
        return InvoiceDetails(
            invoice=invoice,
            business_name=await self.business_name(tenant_id),
            allocated_amount=await self.allocated_amount(tenant_id, invoice.id),
            items=await self.invoice_items(tenant_id, invoice.id),
        )

    async def posted_payment_credit_rows(
        self, tenant_id: UUID, customer_id: UUID
    ) -> list[PaymentCreditRow]:
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
        allocated = (
            select(
                PaymentAllocation.payment_id.label("payment_id"),
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")).label(
                    "allocated_amount"
                ),
            )
            .join(
                Payment,
                (Payment.id == PaymentAllocation.payment_id)
                & (Payment.tenant_id == PaymentAllocation.tenant_id),
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
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                Payment.status == "POSTED",
                not_(is_reversed),
                or_(PaymentAllocation.invoice_id.is_(None), Invoice.status == "ISSUED"),
            )
            .group_by(PaymentAllocation.payment_id)
            .subquery()
        )
        statement = (
            select(Payment, func.coalesce(allocated.c.allocated_amount, Decimal("0.00")))
            .outerjoin(allocated, allocated.c.payment_id == Payment.id)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.customer_id == customer_id,
                Payment.status == "POSTED",
                Payment.amount > func.coalesce(allocated.c.allocated_amount, Decimal("0.00")),
            )
            .order_by(Payment.created_at.asc(), Payment.id.asc())
            .with_for_update(of=Payment)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            PaymentCreditRow(payment=row[0], allocated_amount=cast(Decimal, row[1])) for row in rows
        ]

    async def list_invoices(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID | None,
        invoice_status: InvoiceStatusFilter,
        invoice_sort: InvoiceSort,
        search: str | None,
        issue_date: date | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> InvoicePage:
        allocated_amount = (
            select(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
            .join(
                Payment,
                (Payment.id == PaymentAllocation.payment_id)
                & (Payment.tenant_id == PaymentAllocation.tenant_id),
            )
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                PaymentAllocation.invoice_id == Invoice.id,
                Payment.status == "POSTED",
            )
            .correlate(Invoice)
            .scalar_subquery()
        )
        statement = select(Invoice, allocated_amount).where(Invoice.tenant_id == tenant_id)
        if customer_id is not None:
            statement = statement.where(Invoice.customer_id == customer_id)
        if invoice_status != "all":
            statement = statement.where(Invoice.status == invoice_status.upper())
        if search:
            term = search.strip().lower()
            statement = statement.where(
                or_(
                    func.lower(Invoice.invoice_number).contains(term, autoescape=True),
                    func.lower(Invoice.customer_name_snapshot).contains(term, autoescape=True),
                    func.lower(Invoice.sale_number_snapshot).contains(term, autoescape=True),
                )
            )
        if issue_date is not None:
            statement = statement.where(Invoice.issue_date == issue_date)
        if cursor_created_at is not None and cursor_id is not None:
            comparison = tuple_(Invoice.created_at, Invoice.id)
            statement = statement.where(
                comparison < (cursor_created_at, cursor_id)
                if invoice_sort == "newest"
                else comparison > (cursor_created_at, cursor_id)
            )
        statement = (
            statement.order_by(Invoice.created_at.desc(), Invoice.id.desc())
            if invoice_sort == "newest"
            else statement.order_by(Invoice.created_at.asc(), Invoice.id.asc())
        ).limit(limit + 1)
        rows = (await self.session.execute(statement)).all()
        return InvoicePage(
            items=[
                InvoiceListRow(invoice=row[0], allocated_amount=cast(Decimal, row[1]))
                for row in rows[:limit]
            ],
            has_more=len(rows) > limit,
        )
