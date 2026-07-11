from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.invoices.models import Invoice, InvoiceItem
from distributoros.modules.invoices.pdf import InvoicePdfRenderer
from distributoros.modules.invoices.repository import (
    InvoiceDetails,
    InvoicePage,
    InvoicesRepository,
    SaleInvoiceSource,
)
from distributoros.modules.invoices.schemas import (
    InvoiceCreateRequest,
    InvoiceSort,
    InvoiceStatusFilter,
)
from distributoros.modules.payments.models import PaymentAllocation
from distributoros.modules.sales.service import SalesService
from distributoros.modules.tenancy.models import Business


class InvoicesService:
    def __init__(self, session: AsyncSession, *, pdf_root: str) -> None:
        self.session = session
        self.repository = InvoicesRepository(session)
        self.pdf_root = Path(pdf_root)
        self.logger = structlog.get_logger("distributoros.invoices")

    async def create(
        self,
        request: InvoiceCreateRequest,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> InvoiceDetails:
        key = self._idempotency_key(idempotency_key, "invoice")
        request_hash = self._request_hash(request)
        existing = await self.repository.get_by_create_key(tenant_id, key)
        if existing is not None:
            if existing.create_request_hash != request_hash:
                raise self._idempotency_reused()
            return await self.repository.details(tenant_id, existing)
        invoice: Invoice | None = None
        try:
            async with self.session.begin_nested():
                source = await self.repository.source_for_sale(
                    tenant_id, request.sale_id, for_update=True
                )
                if source is None:
                    raise AppError(
                        status_code=404,
                        code="SALE_NOT_FOUND",
                        message="The selected sale was not found. Refresh sales and try again.",
                        field_errors={"sale_id": "Select a posted sale from this business."},
                    )
                self._validate_source(source)
                business = await self.session.get(Business, tenant_id)
                if business is None:
                    raise AppError(
                        status_code=403,
                        code="BUSINESS_ACCESS_REQUIRED",
                        message="Your business settings are unavailable. Sign in again and retry.",
                    )
                duplicate = await self.repository.get_by_sale(tenant_id, source.sale.id)
                if duplicate is not None:
                    raise AppError(
                        status_code=409,
                        code="INVOICE_ALREADY_EXISTS",
                        message="This sale already has an invoice.",
                        field_errors={"sale_id": "Open the existing invoice for this sale."},
                    )
                invoice_number = await self.repository.next_invoice_number(tenant_id)
                invoice = Invoice(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    invoice_number=invoice_number,
                    sale_id=source.sale.id,
                    ledger_entry_id=source.ledger_entry.id,
                    customer_id=source.customer.id,
                    status="DRAFT",
                    issue_date=date.today(),
                    currency=business.currency,
                    subtotal=source.sale.subtotal,
                    tax_total=source.sale.subtotal * 0,
                    grand_total=source.sale.subtotal,
                    pdf_path=f"{tenant_id}/{invoice_number}.pdf",
                    sale_number_snapshot=source.sale.sale_number,
                    customer_name_snapshot=source.customer.name,
                    customer_phone_snapshot=source.customer.phone,
                    customer_address_line_1_snapshot=source.customer.address_line_1,
                    customer_address_line_2_snapshot=source.customer.address_line_2,
                    customer_city_snapshot=source.customer.city,
                    customer_state_snapshot=source.customer.state,
                    customer_postal_code_snapshot=source.customer.postal_code,
                    created_by=user_id,
                    create_idempotency_key=key,
                    create_request_hash=request_hash,
                )
                self.repository.add_invoice(invoice)
                await self.session.flush()
                self.repository.add_items(
                    [
                        InvoiceItem(
                            id=uuid4(),
                            tenant_id=tenant_id,
                            invoice_id=invoice.id,
                            product_id=item.product_id,
                            line_number=item.line_number,
                            product_snapshot=item.product_name_snapshot,
                            unit_snapshot=item.unit_snapshot,
                            unit_price_snapshot=item.unit_price,
                            quantity_snapshot=item.quantity,
                            line_total=item.line_total,
                        )
                        for item in source.items
                    ]
                )
                await self.session.flush()
        except IntegrityError as exc:
            constraint = _constraint_name(exc)
            if constraint == "uq_invoices_tenant_create_idempotency":
                existing = await self.repository.get_by_create_key(tenant_id, key)
                if existing is None:
                    raise
                if existing.create_request_hash != request_hash:
                    raise self._idempotency_reused() from exc
                return await self.repository.details(tenant_id, existing)
            if constraint == "uq_invoices_tenant_sale":
                raise AppError(
                    status_code=409,
                    code="INVOICE_ALREADY_EXISTS",
                    message="This sale already has an invoice.",
                    field_errors={"sale_id": "Open the existing invoice for this sale."},
                ) from exc
            if constraint == "uq_invoices_tenant_invoice_number":
                raise AppError(
                    status_code=409,
                    code="INVOICE_NUMBER_ALREADY_EXISTS",
                    message="An invoice with this number already exists. Try again.",
                ) from exc
            raise
        if invoice is None:
            raise RuntimeError("Invoice creation did not produce an invoice.")
        details = await self.repository.details(tenant_id, invoice)
        self.logger.info(
            "invoice_created",
            tenant_id=str(tenant_id),
            invoice_id=str(invoice.id),
            invoice_number=invoice.invoice_number,
            sale_id=str(invoice.sale_id),
            user_id=str(user_id),
        )
        return details

    async def issue(
        self,
        invoice_id: UUID,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> InvoiceDetails:
        key = self._idempotency_key(idempotency_key, "invoice")
        try:
            async with self.session.begin_nested():
                invoice = self._require_invoice(
                    await self.repository.get_for_update(tenant_id, invoice_id)
                )
                if invoice.status == "ISSUED":
                    if invoice.issue_idempotency_key == key:
                        return await self.repository.details(tenant_id, invoice)
                    raise AppError(
                        status_code=409,
                        code="INVOICE_ALREADY_ISSUED",
                        message="This invoice has already been issued.",
                    )
                if invoice.status == "VOID":
                    raise AppError(
                        status_code=409,
                        code="INVOICE_ALREADY_VOIDED",
                        message="This invoice has already been voided.",
                    )
                source = await self.repository.source_for_sale(
                    tenant_id, invoice.sale_id, for_update=True
                )
                if source is None:
                    raise self._corrupt_invoice()
                self._validate_source(source)
                invoice.status = "ISSUED"
                invoice.issue_idempotency_key = key
                await self.session.flush()
                await self._auto_allocate_credit(invoice, tenant_id=tenant_id)
                await self.session.flush()
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_invoices_tenant_issue_idempotency":
                raise self._idempotency_reused() from exc
            raise
        details = await self.repository.details(tenant_id, invoice)
        self.logger.info(
            "invoice_issued",
            tenant_id=str(tenant_id),
            invoice_id=str(invoice.id),
            invoice_number=invoice.invoice_number,
            user_id=str(user_id),
        )
        return details

    async def void(
        self,
        invoice_id: UUID,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> InvoiceDetails:
        key = self._idempotency_key(idempotency_key, "invoice")
        try:
            async with self.session.begin_nested():
                invoice = self._require_invoice(
                    await self.repository.get_for_update(tenant_id, invoice_id)
                )
                if invoice.status == "VOID":
                    if invoice.void_idempotency_key == key:
                        return await self.repository.details(tenant_id, invoice)
                    raise AppError(
                        status_code=409,
                        code="INVOICE_ALREADY_VOIDED",
                        message="This invoice has already been voided.",
                    )
                if invoice.status != "ISSUED":
                    raise AppError(
                        status_code=409,
                        code="INVOICE_NOT_ISSUED",
                        message="Only an issued invoice can be voided.",
                    )
                source = await self.repository.source_for_sale(
                    tenant_id, invoice.sale_id, for_update=True
                )
                if source is None:
                    raise self._corrupt_invoice()
                if source.sale.status == "POSTED":
                    await SalesService(self.session).void(
                        source.sale.id,
                        idempotency_key=self._child_idempotency_key(key, invoice.id),
                        tenant_id=tenant_id,
                        user_id=user_id,
                        allow_invoiced=True,
                    )
                elif source.sale.status != "VOID":
                    raise self._corrupt_invoice()
                invoice.status = "VOID"
                invoice.void_idempotency_key = key
                self._remove_cached_pdf(invoice)
                await self.session.flush()
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_invoices_tenant_void_idempotency":
                raise self._idempotency_reused() from exc
            raise
        details = await self.repository.details(tenant_id, invoice)
        self.logger.info(
            "invoice_voided",
            tenant_id=str(tenant_id),
            invoice_id=str(invoice.id),
            invoice_number=invoice.invoice_number,
            user_id=str(user_id),
        )
        return details

    async def get(self, invoice_id: UUID, *, tenant_id: UUID) -> InvoiceDetails:
        invoice = self._require_invoice(await self.repository.get(tenant_id, invoice_id))
        return await self.repository.details(tenant_id, invoice)

    async def get_by_number(self, invoice_number: str, *, tenant_id: UUID) -> InvoiceDetails:
        invoice = self._require_invoice(
            await self.repository.get_by_number(tenant_id, invoice_number)
        )
        return await self.repository.details(tenant_id, invoice)

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
        cursor: str | None,
    ) -> tuple[InvoicePage, str | None]:
        if (
            customer_id is not None
            and await self.repository.get_customer(tenant_id, customer_id) is None
        ):
            raise AppError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="Customer not found.",
            )
        cursor_created, cursor_id = self._decode_cursor(
            cursor,
            customer_id=customer_id,
            invoice_status=invoice_status,
            invoice_sort=invoice_sort,
            search=search,
            issue_date=issue_date,
        )
        page = await self.repository.list_invoices(
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_status=invoice_status,
            invoice_sort=invoice_sort,
            search=search,
            issue_date=issue_date,
            limit=limit,
            cursor_created_at=cursor_created,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1].invoice
            next_cursor = self._encode_cursor(
                created_at=last.created_at,
                invoice_id=last.id,
                customer_id=customer_id,
                invoice_status=invoice_status,
                invoice_sort=invoice_sort,
                search=search,
                issue_date=issue_date,
            )
        return page, next_cursor

    async def pdf_bytes(self, invoice_id: UUID, *, tenant_id: UUID) -> tuple[InvoiceDetails, bytes]:
        invoice = self._require_invoice(await self.repository.get(tenant_id, invoice_id))
        details = await self.repository.details(tenant_id, invoice)
        path = self._pdf_file(invoice)
        content = InvoicePdfRenderer().render(details)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return details, content

    async def _auto_allocate_credit(self, invoice: Invoice, *, tenant_id: UUID) -> None:
        outstanding = invoice.grand_total - await self.repository.allocated_amount(
            tenant_id, invoice.id
        )
        if outstanding <= 0:
            return
        for row in await self.repository.posted_payment_credit_rows(tenant_id, invoice.customer_id):
            if outstanding <= 0:
                break
            amount = min(outstanding, row.remaining_amount)
            if amount <= 0:
                continue
            self.repository.add_allocations(
                [
                    PaymentAllocation(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        payment_id=row.payment.id,
                        ledger_entry_id=invoice.ledger_entry_id,
                        invoice_id=invoice.id,
                        allocated_amount=amount,
                    )
                ]
            )
            outstanding -= amount

    @staticmethod
    def _validate_source(source: SaleInvoiceSource) -> None:
        sale = source.sale
        customer = source.customer
        items = source.items
        if sale.status != "POSTED":
            raise AppError(
                status_code=422,
                code="SALE_NOT_POSTED",
                message="Only a posted sale can be invoiced.",
                field_errors={"sale_id": "Post the sale before creating an invoice."},
            )
        if customer.archived:
            raise AppError(
                status_code=422,
                code="CUSTOMER_ARCHIVED",
                message="The sale customer is archived. Restore the customer before invoicing.",
                field_errors={"sale_id": "Restore the sale customer and try again."},
            )
        if not items:
            raise AppError(
                status_code=422,
                code="SALE_ITEMS_REQUIRED",
                message="The selected sale has no items and cannot be invoiced.",
                field_errors={"sale_id": "Select a posted sale with at least one item."},
            )

    def _pdf_file(self, invoice: Invoice) -> Path:
        relative = Path(invoice.pdf_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise self._corrupt_invoice()
        return self.pdf_root / relative

    def _remove_cached_pdf(self, invoice: Invoice) -> None:
        path = self._pdf_file(invoice)
        if path.exists():
            path.unlink()

    @staticmethod
    def _require_invoice(invoice: Invoice | None) -> Invoice:
        if invoice is None:
            raise AppError(
                status_code=404,
                code="INVOICE_NOT_FOUND",
                message="This invoice was not found. Refresh invoices and try again.",
            )
        return invoice

    @staticmethod
    def _idempotency_key(value: str | None, noun: str) -> str:
        if value is None or not value.strip():
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_REQUIRED",
                message=f"A submission key is required. Submit the {noun} again.",
                field_errors={"idempotency_key": "Submit again to generate a new key."},
            )
        key = value.strip()
        if len(key) > 128:
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_INVALID",
                message=f"The submission key is too long. Submit the {noun} again.",
                field_errors={"idempotency_key": "Submission key is too long."},
            )
        return key

    @staticmethod
    def _request_hash(request: InvoiceCreateRequest) -> str:
        raw = json.dumps(
            {"sale_id": str(request.sale_id)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _idempotency_reused() -> AppError:
        return AppError(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message=(
                "This submission key was already used for a different invoice operation. "
                "Submit again to generate a new key."
            ),
            field_errors={"idempotency_key": "Use a new submission key and try again."},
        )

    @staticmethod
    def _child_idempotency_key(parent_key: str, invoice_id: UUID) -> str:
        digest = hashlib.sha256(f"{invoice_id}:{parent_key}".encode()).hexdigest()
        return f"invoice-void-{digest[:32]}"

    @staticmethod
    def _corrupt_invoice() -> AppError:
        return AppError(
            status_code=409,
            code="INVOICE_STATE_CORRUPT",
            message="This invoice is inconsistent. Contact support before trying again.",
        )

    @staticmethod
    def _fingerprint(
        *,
        customer_id: UUID | None,
        invoice_status: InvoiceStatusFilter,
        invoice_sort: InvoiceSort,
        search: str | None,
        issue_date: date | None,
    ) -> str:
        return json.dumps(
            {
                "customer_id": str(customer_id) if customer_id else None,
                "status": invoice_status,
                "sort": invoice_sort,
                "search": search or "",
                "date": issue_date.isoformat() if issue_date else None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def _encode_cursor(
        cls,
        *,
        created_at: datetime,
        invoice_id: UUID,
        customer_id: UUID | None,
        invoice_status: InvoiceStatusFilter,
        invoice_sort: InvoiceSort,
        search: str | None,
        issue_date: date | None,
    ) -> str:
        payload = {
            "created_at": created_at.astimezone(UTC).isoformat(),
            "id": str(invoice_id),
            "fingerprint": cls._fingerprint(
                customer_id=customer_id,
                invoice_status=invoice_status,
                invoice_sort=invoice_sort,
                search=search,
                issue_date=issue_date,
            ),
        }
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    @classmethod
    def _decode_cursor(
        cls,
        cursor: str | None,
        *,
        customer_id: UUID | None,
        invoice_status: InvoiceStatusFilter,
        invoice_sort: InvoiceSort,
        search: str | None,
        issue_date: date | None,
    ) -> tuple[datetime | None, UUID | None]:
        if not cursor:
            return None, None
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            expected = cls._fingerprint(
                customer_id=customer_id,
                invoice_status=invoice_status,
                invoice_sort=invoice_sort,
                search=search,
                issue_date=issue_date,
            )
            if payload.get("fingerprint") != expected:
                raise ValueError
            return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_INVOICE_CURSOR",
                message="The invoice list changed. Refresh invoices before loading more.",
                field_errors={"cursor": "Refresh invoices and try again."},
            ) from exc


def _constraint_name(exc: IntegrityError) -> str | None:
    original = getattr(exc, "orig", None)
    return cast(str | None, getattr(original, "constraint_name", None))
