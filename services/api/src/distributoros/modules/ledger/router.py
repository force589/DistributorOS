from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.ledger.repository import LedgerListRow
from distributoros.modules.ledger.schemas import (
    CustomerFinancialSummaryResponse,
    LedgerEntryResponse,
    LedgerEntryTypeFilter,
    LedgerListResponse,
)
from distributoros.modules.ledger.service import LedgerQueryService

router = APIRouter(prefix="/customers", tags=["Customer Ledger"])


def _entry_response(row: LedgerListRow) -> LedgerEntryResponse:
    return LedgerEntryResponse(
        id=row.id,
        entry_type=row.entry_type,
        reference_type=row.reference_type,
        reference_id=row.reference_id,
        reference=row.reference,
        debit=row.debit,
        credit=row.credit,
        running_balance=row.running_balance,
        remarks=row.remarks,
        created_at=row.created_at,
    )


@router.get(
    "/{customer_id}/financial-summary",
    response_model=CustomerFinancialSummaryResponse,
)
async def get_customer_financial_summary(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerFinancialSummaryResponse:
    projection = await LedgerQueryService(session).summary(
        tenant_id=principal.business.id,
        customer_id=customer_id,
    )
    return CustomerFinancialSummaryResponse(
        customer_id=customer_id,
        outstanding_balance=(projection.outstanding_balance if projection else Decimal("0.00")),
        available_credit=projection.available_credit if projection else Decimal("0.00"),
        total_sales=projection.total_sales if projection else Decimal("0.00"),
        total_payments=projection.total_payments if projection else Decimal("0.00"),
        last_sale_date=projection.last_sale_at if projection else None,
        last_payment_date=projection.last_payment_at if projection else None,
    )


async def _ledger_list(
    *,
    customer_id: UUID,
    principal: Principal,
    session: AsyncSession,
    entry_type: LedgerEntryTypeFilter,
    reference: str | None,
    ledger_date: date | None,
    limit: int,
    cursor: str | None,
) -> LedgerListResponse:
    page, next_cursor = await LedgerQueryService(session).list_entries(
        tenant_id=principal.business.id,
        customer_id=customer_id,
        entry_type=entry_type,
        reference=reference.strip() if reference and reference.strip() else None,
        ledger_date=ledger_date,
        limit=limit,
        cursor=cursor,
    )
    return LedgerListResponse(
        items=[_entry_response(row) for row in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("/{customer_id}/ledger", response_model=LedgerListResponse)
async def list_customer_ledger(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    entry_type: Annotated[LedgerEntryTypeFilter, Query(alias="entry_type")] = "all",
    reference: Annotated[str | None, Query(max_length=160)] = None,
    ledger_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> LedgerListResponse:
    return await _ledger_list(
        customer_id=customer_id,
        principal=principal,
        session=session,
        entry_type=entry_type,
        reference=reference,
        ledger_date=ledger_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{customer_id}/ledger/search", response_model=LedgerListResponse)
async def search_customer_ledger(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    reference: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    entry_type: Annotated[LedgerEntryTypeFilter, Query(alias="entry_type")] = "all",
    ledger_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> LedgerListResponse:
    if not (reference and reference.strip()) and entry_type == "all" and ledger_date is None:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Enter a sale or payment reference, or choose a ledger date or entry type.",
            field_errors={"q": "Enter a sale or payment reference to search."},
        )
    return await _ledger_list(
        customer_id=customer_id,
        principal=principal,
        session=session,
        entry_type=entry_type,
        reference=reference,
        ledger_date=ledger_date,
        limit=limit,
        cursor=cursor,
    )
