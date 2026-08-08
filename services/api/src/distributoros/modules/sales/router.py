from datetime import date
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.sales.repository import SaleDetails, SaleListRow
from distributoros.modules.sales.schemas import (
    SaleCreateRequest,
    SaleItemResponse,
    SaleListItemResponse,
    SaleListResponse,
    SaleMutationResponse,
    SaleResponse,
    SaleSort,
    SaleStatus,
    SaleStatusFilter,
    SaleUpdateRequest,
)
from distributoros.modules.sales.service import SalesService

router = APIRouter(prefix="/sales", tags=["Sales"])


def _sale_response(details: SaleDetails) -> SaleResponse:
    sale = details.sale
    return SaleResponse(
        id=sale.id,
        sale_number=sale.sale_number,
        customer_id=sale.customer_id,
        customer_name=details.customer_name,
        status=cast(SaleStatus, sale.status),
        subtotal=sale.subtotal,
        created_at=sale.created_at,
        created_by=sale.created_by,
        updated_at=sale.updated_at,
        items=[SaleItemResponse.model_validate(item) for item in details.items],
    )


def _list_item(row: SaleListRow) -> SaleListItemResponse:
    sale = row.sale
    return SaleListItemResponse(
        id=sale.id,
        sale_number=sale.sale_number,
        customer_id=sale.customer_id,
        customer_name=row.customer_name,
        status=cast(SaleStatus, sale.status),
        subtotal=sale.subtotal,
        item_count=row.item_count,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
    )


@router.post("", response_model=SaleMutationResponse, status_code=status.HTTP_201_CREATED)
async def create_sale(
    payload: SaleCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SaleMutationResponse:
    details = await SalesService(session).create(
        payload,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return SaleMutationResponse(
        sale=_sale_response(details), message="Sale draft created successfully."
    )


async def _list_sales(
    *,
    principal: Principal,
    session: AsyncSession,
    sale_status: SaleStatusFilter,
    sale_sort: SaleSort,
    search: str | None,
    sale_date: date | None,
    limit: int,
    cursor: str | None,
) -> SaleListResponse:
    page, next_cursor = await SalesService(session).list_sales(
        tenant_id=principal.business.id,
        timezone=principal.business.timezone,
        sale_status=sale_status,
        sale_sort=sale_sort,
        search=search.strip() if search and search.strip() else None,
        sale_date=sale_date,
        limit=limit,
        cursor=cursor,
    )
    return SaleListResponse(
        items=[_list_item(row) for row in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("", response_model=SaleListResponse)
async def list_sales(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sale_status: Annotated[SaleStatusFilter, Query(alias="status")] = "all",
    sale_sort: Annotated[SaleSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    sale_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> SaleListResponse:
    return await _list_sales(
        principal=principal,
        session=session,
        sale_status=sale_status,
        sale_sort=sale_sort,
        search=search,
        sale_date=sale_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/search", response_model=SaleListResponse)
async def search_sales(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    sale_status: Annotated[SaleStatusFilter, Query(alias="status")] = "all",
    sale_sort: Annotated[SaleSort, Query(alias="sort")] = "newest",
    sale_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> SaleListResponse:
    if not (query and query.strip()) and sale_status == "all" and sale_date is None:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Enter a sale number or customer, or choose a date or status.",
            field_errors={"q": "Enter a sale number or customer to search."},
        )
    return await _list_sales(
        principal=principal,
        session=session,
        sale_status=sale_status,
        sale_sort=sale_sort,
        search=query,
        sale_date=sale_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/number/{sale_number}", response_model=SaleResponse)
async def get_sale_by_number(
    sale_number: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SaleResponse:
    return _sale_response(
        await SalesService(session).get_by_number(sale_number, tenant_id=principal.business.id)
    )


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SaleResponse:
    return _sale_response(await SalesService(session).get(sale_id, tenant_id=principal.business.id))


@router.patch("/{sale_id}", response_model=SaleMutationResponse)
async def update_sale(
    sale_id: UUID,
    payload: SaleUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SaleMutationResponse:
    details = await SalesService(session).update(
        sale_id,
        payload,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return SaleMutationResponse(
        sale=_sale_response(details), message="Sale draft updated successfully."
    )


@router.post("/{sale_id}/post", response_model=SaleMutationResponse)
async def post_sale(
    sale_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SaleMutationResponse:
    details = await SalesService(session).post(
        sale_id,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return SaleMutationResponse(sale=_sale_response(details), message="Sale posted successfully.")


@router.post("/{sale_id}/void", response_model=SaleMutationResponse)
async def void_sale(
    sale_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SaleMutationResponse:
    details = await SalesService(session).void(
        sale_id,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return SaleMutationResponse(
        sale=_sale_response(details), message="Sale voided and inventory restored successfully."
    )
