from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.inventory.repository import MovementRow, StockRow
from distributoros.modules.inventory.schemas import (
    AdjustmentRequest,
    InventoryMutationResponse,
    MovementHistoryResponse,
    MovementType,
    PositiveStockRequest,
    StockItemResponse,
    StockListResponse,
    StockMovementResponse,
    WarehouseResponse,
)
from distributoros.modules.inventory.service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _movement_response(row: MovementRow) -> StockMovementResponse:
    movement = row.movement
    return StockMovementResponse(
        id=movement.id,
        product_id=movement.product_id,
        product_code=row.product.product_code,
        product_name=row.product.name,
        warehouse_id=movement.warehouse_id,
        warehouse_name=row.warehouse.name,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        unit=movement.unit,
        reference_type=movement.reference_type,
        reference_id=movement.reference_id,
        remarks=movement.remarks,
        created_at=movement.created_at,
        created_by=movement.created_by,
        created_by_email=row.created_by_email,
    )


def _stock_response(row: StockRow) -> StockItemResponse:
    return StockItemResponse(
        product_id=row.product.id,
        product_code=row.product.product_code,
        product_name=row.product.name,
        warehouse_id=row.warehouse.id,
        warehouse_name=row.warehouse.name,
        available_quantity=row.available_quantity,
        unit=row.product.unit,
        low_stock_threshold=row.product.low_stock_threshold,
        low_stock_status=InventoryService.low_stock_status(
            row.available_quantity, row.product.low_stock_threshold
        ),
        updated_at=row.updated_at,
    )


async def _post_positive(
    *,
    payload: PositiveStockRequest,
    movement_type: MovementType,
    success_message: str,
    idempotency_key: str | None,
    principal: Principal,
    session: AsyncSession,
) -> InventoryMutationResponse:
    movement, stock = await InventoryService(session).post_positive(
        payload,
        movement_type=movement_type,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return InventoryMutationResponse(
        movement=_movement_response(movement),
        stock=_stock_response(stock),
        message=success_message,
    )


@router.post(
    "/opening-stock",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_opening_stock(
    payload: PositiveStockRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InventoryMutationResponse:
    return await _post_positive(
        payload=payload,
        movement_type="OPENING_STOCK",
        success_message="Opening stock recorded successfully.",
        idempotency_key=idempotency_key,
        principal=principal,
        session=session,
    )


@router.post(
    "/stock-receipts",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_receipt(
    payload: PositiveStockRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InventoryMutationResponse:
    return await _post_positive(
        payload=payload,
        movement_type="STOCK_RECEIPT",
        success_message="Stock receipt recorded successfully.",
        idempotency_key=idempotency_key,
        principal=principal,
        session=session,
    )


@router.post(
    "/adjustments",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_adjustment(
    payload: AdjustmentRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InventoryMutationResponse:
    movement, stock = await InventoryService(session).post_adjustment(
        payload,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return InventoryMutationResponse(
        movement=_movement_response(movement),
        stock=_stock_response(stock),
        message="Stock adjustment recorded successfully.",
    )


@router.post(
    "/customer-returns",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_return(
    payload: PositiveStockRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InventoryMutationResponse:
    return await _post_positive(
        payload=payload,
        movement_type="CUSTOMER_RETURN",
        success_message="Customer return recorded successfully.",
        idempotency_key=idempotency_key,
        principal=principal,
        session=session,
    )


@router.post(
    "/damage",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_damage_entry(
    payload: PositiveStockRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InventoryMutationResponse:
    return await _post_positive(
        payload=payload,
        movement_type="DAMAGED",
        success_message="Damaged stock recorded successfully.",
        idempotency_key=idempotency_key,
        principal=principal,
        session=session,
    )


@router.post(
    "/spoilage",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_spoilage_entry(
    payload: PositiveStockRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InventoryMutationResponse:
    return await _post_positive(
        payload=payload,
        movement_type="SPOILAGE",
        success_message="Spoiled stock recorded successfully.",
        idempotency_key=idempotency_key,
        principal=principal,
        session=session,
    )


@router.get("/stock", response_model=StockListResponse)
async def list_stock(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    warehouse_id: Annotated[UUID | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> StockListResponse:
    page, next_cursor = await InventoryService(session).list_stock(
        tenant_id=principal.business.id,
        warehouse_id=warehouse_id,
        search=search.strip() if search and search.strip() else None,
        limit=limit,
        cursor=cursor,
    )
    return StockListResponse(
        items=[_stock_response(row) for row in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("/stock/{product_id}", response_model=StockItemResponse)
async def get_current_stock(
    product_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    warehouse_id: Annotated[UUID | None, Query()] = None,
) -> StockItemResponse:
    row = await InventoryService(session).get_current_stock(
        tenant_id=principal.business.id,
        product_id=product_id,
        warehouse_id=warehouse_id,
    )
    return _stock_response(row)


@router.get("/history", response_model=MovementHistoryResponse)
async def inventory_history(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    warehouse_id: Annotated[UUID | None, Query()] = None,
    product_id: Annotated[UUID | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> MovementHistoryResponse:
    page, next_cursor = await InventoryService(session).list_history(
        tenant_id=principal.business.id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        search=search.strip() if search and search.strip() else None,
        limit=limit,
        cursor=cursor,
    )
    return MovementHistoryResponse(
        items=[_movement_response(row) for row in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("/warehouses/default", response_model=WarehouseResponse)
async def get_default_warehouse(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WarehouseResponse:
    warehouse = await InventoryService(session).default_warehouse(principal.business.id)
    return WarehouseResponse.model_validate(warehouse)
