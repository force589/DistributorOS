from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.config import Settings, get_settings
from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.invoices.repository import InvoiceDetails, InvoiceListRow
from distributoros.modules.invoices.schemas import (
    InvoiceCreateRequest,
    InvoiceItemResponse,
    InvoiceListItemResponse,
    InvoiceListResponse,
    InvoiceMutationResponse,
    InvoiceResponse,
    InvoiceSort,
    InvoiceStatusFilter,
)
from distributoros.modules.invoices.service import InvoicesService

router = APIRouter(tags=["Invoices"])


def _invoice_response(details: InvoiceDetails) -> InvoiceResponse:
    invoice = details.invoice
    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        sale_id=invoice.sale_id,
        sale_number=invoice.sale_number_snapshot,
        customer_id=invoice.customer_id,
        status=invoice.status,
        issue_date=invoice.issue_date,
        currency=invoice.currency,
        subtotal=invoice.subtotal,
        tax_total=invoice.tax_total,
        grand_total=invoice.grand_total,
        allocated_amount=details.allocated_amount,
        outstanding_amount=details.outstanding_amount,
        pdf_path=invoice.pdf_path,
        customer_name_snapshot=invoice.customer_name_snapshot,
        customer_phone_snapshot=invoice.customer_phone_snapshot,
        customer_address_line_1_snapshot=invoice.customer_address_line_1_snapshot,
        customer_address_line_2_snapshot=invoice.customer_address_line_2_snapshot,
        customer_city_snapshot=invoice.customer_city_snapshot,
        customer_state_snapshot=invoice.customer_state_snapshot,
        customer_postal_code_snapshot=invoice.customer_postal_code_snapshot,
        created_at=invoice.created_at,
        created_by=invoice.created_by,
        items=[InvoiceItemResponse.model_validate(item) for item in details.items],
    )


def _list_item(row: InvoiceListRow) -> InvoiceListItemResponse:
    invoice = row.invoice
    return InvoiceListItemResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        sale_id=invoice.sale_id,
        sale_number=invoice.sale_number_snapshot,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer_name_snapshot,
        status=invoice.status,
        issue_date=invoice.issue_date,
        currency=invoice.currency,
        grand_total=invoice.grand_total,
        allocated_amount=row.allocated_amount,
        outstanding_amount=row.outstanding_amount,
        created_at=invoice.created_at,
    )


def _service(session: AsyncSession, settings: Settings) -> InvoicesService:
    return InvoicesService(session, pdf_root=settings.invoice_pdf_root)


@router.post(
    "/invoices",
    response_model=InvoiceMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    payload: InvoiceCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvoiceMutationResponse:
    details = await _service(session, settings).create(
        payload,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return InvoiceMutationResponse(
        invoice=_invoice_response(details),
        message="Invoice draft created successfully.",
    )


async def _list_invoices(
    *,
    principal: Principal,
    session: AsyncSession,
    settings: Settings,
    customer_id: UUID | None,
    invoice_status: InvoiceStatusFilter,
    invoice_sort: InvoiceSort,
    search: str | None,
    issue_date: date | None,
    limit: int,
    cursor: str | None,
) -> InvoiceListResponse:
    page, next_cursor = await _service(session, settings).list_invoices(
        tenant_id=principal.business.id,
        customer_id=customer_id,
        invoice_status=invoice_status,
        invoice_sort=invoice_sort,
        search=search.strip() if search and search.strip() else None,
        issue_date=issue_date,
        limit=limit,
        cursor=cursor,
    )
    return InvoiceListResponse(
        items=[_list_item(row) for row in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    invoice_status: Annotated[InvoiceStatusFilter, Query(alias="status")] = "all",
    invoice_sort: Annotated[InvoiceSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    issue_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> InvoiceListResponse:
    return await _list_invoices(
        principal=principal,
        session=session,
        settings=settings,
        customer_id=None,
        invoice_status=invoice_status,
        invoice_sort=invoice_sort,
        search=search,
        issue_date=issue_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/invoices/search", response_model=InvoiceListResponse)
async def search_invoices(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    query: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    invoice_status: Annotated[InvoiceStatusFilter, Query(alias="status")] = "all",
    invoice_sort: Annotated[InvoiceSort, Query(alias="sort")] = "newest",
    issue_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> InvoiceListResponse:
    if not (query and query.strip()) and invoice_status == "all" and issue_date is None:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Enter an invoice number, sale number, customer, date, or status.",
            field_errors={"q": "Enter invoice search text or choose a filter."},
        )
    return await _list_invoices(
        principal=principal,
        session=session,
        settings=settings,
        customer_id=None,
        invoice_status=invoice_status,
        invoice_sort=invoice_sort,
        search=query,
        issue_date=issue_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/invoices/number/{invoice_number}", response_model=InvoiceResponse)
async def get_invoice_by_number(
    invoice_number: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvoiceResponse:
    return _invoice_response(
        await _service(session, settings).get_by_number(
            invoice_number, tenant_id=principal.business.id
        )
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvoiceResponse:
    return _invoice_response(
        await _service(session, settings).get(invoice_id, tenant_id=principal.business.id)
    )


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceMutationResponse)
async def issue_invoice(
    invoice_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvoiceMutationResponse:
    details = await _service(session, settings).issue(
        invoice_id,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return InvoiceMutationResponse(
        invoice=_invoice_response(details),
        message="Invoice issued successfully.",
    )


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceMutationResponse)
async def void_invoice(
    invoice_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvoiceMutationResponse:
    details = await _service(session, settings).void(
        invoice_id,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return InvoiceMutationResponse(
        invoice=_invoice_response(details),
        message="Invoice voided successfully.",
    )


@router.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    details, content = await _service(session, settings).pdf_bytes(
        invoice_id, tenant_id=principal.business.id
    )
    filename = f"{details.invoice.invoice_number}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/customers/{customer_id}/invoices", response_model=InvoiceListResponse)
async def list_customer_invoices(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    invoice_status: Annotated[InvoiceStatusFilter, Query(alias="status")] = "all",
    invoice_sort: Annotated[InvoiceSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    issue_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> InvoiceListResponse:
    return await _list_invoices(
        principal=principal,
        session=session,
        settings=settings,
        customer_id=customer_id,
        invoice_status=invoice_status,
        invoice_sort=invoice_sort,
        search=search,
        issue_date=issue_date,
        limit=limit,
        cursor=cursor,
    )
