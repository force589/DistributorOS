from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.config import Settings, get_settings
from distributoros.core.database import get_session
from distributoros.core.rate_limit import enforce_rate_limit
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.insights.schemas import (
    DashboardResponse,
    GlobalSearchResponse,
    InventoryReportResponse,
    InventoryReportSort,
    LowStockReportResponse,
    LowStockReportSort,
    OutstandingReportResponse,
    OutstandingReportSort,
    PaymentReportResponse,
    PaymentReportSort,
    ReportPeriod,
    ReportStatusFilter,
    SalesReportResponse,
    SalesReportSort,
)
from distributoros.modules.insights.service import InsightsService

router = APIRouter(tags=["Insights"])


def _service(session: AsyncSession) -> InsightsService:
    return InsightsService(session)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DashboardResponse:
    return await _service(session).dashboard(principal.business.id)


@router.get("/search", response_model=GlobalSearchResponse)
async def global_search(
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    query: Annotated[str, Query(alias="q", max_length=120)] = "",
    limit_per_group: Annotated[int, Query(ge=1, le=10)] = 5,
) -> GlobalSearchResponse:
    await enforce_rate_limit(
        request,
        settings,
        scope="insights.global_search",
        identity=f"{principal.business.id}:{principal.user.id}",
        limit=settings.search_rate_limit,
        window_seconds=60,
    )
    return await _service(session).global_search(
        principal.business.id,
        query,
        limit_per_group=limit_per_group,
    )


@router.get("/reports/sales", response_model=SalesReportResponse)
async def sales_report(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    period: ReportPeriod = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    status: ReportStatusFilter = "all",
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: SalesReportSort = "newest",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1200)] = None,
) -> SalesReportResponse:
    return await _service(session).sales_report(
        principal.business.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        status=status,
        search=search,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("/reports/payments", response_model=PaymentReportResponse)
async def payments_report(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    period: ReportPeriod = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    status: ReportStatusFilter = "all",
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: PaymentReportSort = "newest",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1200)] = None,
) -> PaymentReportResponse:
    return await _service(session).payments_report(
        principal.business.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        status=status,
        search=search,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("/reports/outstanding", response_model=OutstandingReportResponse)
async def outstanding_report(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: OutstandingReportSort = "highest_outstanding",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1200)] = None,
) -> OutstandingReportResponse:
    return await _service(session).outstanding_report(
        principal.business.id,
        search=search,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("/reports/inventory", response_model=InventoryReportResponse)
async def inventory_report(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: InventoryReportSort = "name_asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1200)] = None,
) -> InventoryReportResponse:
    return await _service(session).inventory_report(
        principal.business.id,
        search=search,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("/reports/low-stock", response_model=LowStockReportResponse)
async def low_stock_report(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: LowStockReportSort = "lowest_stock",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1200)] = None,
) -> LowStockReportResponse:
    return await _service(session).low_stock_report(
        principal.business.id,
        search=search,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("/reports/sales.csv")
async def sales_csv(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    period: ReportPeriod = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    status: ReportStatusFilter = "all",
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: SalesReportSort = "newest",
) -> Response:
    export = await _service(session).sales_csv(
        principal.business.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        status=status,
        search=search,
        sort=sort,
    )
    return _csv_response(export.filename, export.content)


@router.get("/reports/payments.csv")
async def payments_csv(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    period: ReportPeriod = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    status: ReportStatusFilter = "all",
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: PaymentReportSort = "newest",
) -> Response:
    export = await _service(session).payments_csv(
        principal.business.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        status=status,
        search=search,
        sort=sort,
    )
    return _csv_response(export.filename, export.content)


@router.get("/reports/outstanding.csv")
async def outstanding_csv(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: OutstandingReportSort = "highest_outstanding",
) -> Response:
    export = await _service(session).outstanding_csv(
        principal.business.id,
        search=search,
        sort=sort,
    )
    return _csv_response(export.filename, export.content)


@router.get("/reports/inventory.csv")
async def inventory_csv(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: InventoryReportSort = "name_asc",
) -> Response:
    export = await _service(session).inventory_csv(
        principal.business.id,
        search=search,
        sort=sort,
    )
    return _csv_response(export.filename, export.content)


@router.get("/reports/low-stock.csv")
async def low_stock_csv(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: LowStockReportSort = "lowest_stock",
) -> Response:
    export = await _service(session).low_stock_csv(
        principal.business.id,
        search=search,
        sort=sort,
    )
    return _csv_response(export.filename, export.content)


def _csv_response(filename: str, content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
