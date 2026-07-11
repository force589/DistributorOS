from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.products.schemas import (
    ProductCreateRequest,
    ProductListResponse,
    ProductMutationResponse,
    ProductResponse,
    ProductSort,
    ProductStatus,
    ProductUpdateRequest,
)
from distributoros.modules.products.service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductMutationResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductMutationResponse:
    product = await ProductService(session).create(
        payload,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return ProductMutationResponse(
        product=ProductResponse.model_validate(product),
        message="Product created successfully.",
    )


async def _list_products(
    *,
    principal: Principal,
    session: AsyncSession,
    product_status: ProductStatus,
    product_sort: ProductSort,
    search: str | None,
    limit: int,
    cursor: str | None,
) -> ProductListResponse:
    normalized_search = search.strip() if search else None
    page, next_cursor = await ProductService(session).list(
        tenant_id=principal.business.id,
        product_status=product_status,
        product_sort=product_sort,
        search=normalized_search or None,
        limit=limit,
        cursor=cursor,
    )
    return ProductListResponse(
        items=[ProductResponse.model_validate(product) for product in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    product_status: Annotated[ProductStatus, Query(alias="status")] = "active",
    product_sort: Annotated[ProductSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> ProductListResponse:
    return await _list_products(
        principal=principal,
        session=session,
        product_status=product_status,
        product_sort=product_sort,
        search=search,
        limit=limit,
        cursor=cursor,
    )


@router.get("/search", response_model=ProductListResponse)
async def search_products(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str, Query(alias="q", min_length=1, max_length=160)],
    product_status: Annotated[ProductStatus, Query(alias="status")] = "active",
    product_sort: Annotated[ProductSort, Query(alias="sort")] = "name_asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> ProductListResponse:
    if not query.strip():
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Enter a product name, code, SKU, barcode, or category.",
            field_errors={"q": "Enter a product name, code, SKU, barcode, or category."},
        )
    return await _list_products(
        principal=principal,
        session=session,
        product_status=product_status,
        product_sort=product_sort,
        search=query,
        limit=limit,
        cursor=cursor,
    )


@router.get("/code/{product_code}", response_model=ProductResponse)
async def get_product_by_code(
    product_code: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductResponse:
    product = await ProductService(session).get_by_code(
        product_code,
        tenant_id=principal.business.id,
    )
    return ProductResponse.model_validate(product)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductResponse:
    product = await ProductService(session).get(product_id, tenant_id=principal.business.id)
    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductMutationResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductMutationResponse:
    product = await ProductService(session).update(
        product_id,
        payload,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return ProductMutationResponse(
        product=ProductResponse.model_validate(product),
        message="Product updated successfully.",
    )


@router.post("/{product_id}/archive", response_model=ProductMutationResponse)
async def archive_product(
    product_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductMutationResponse:
    product = await ProductService(session).set_archived(
        product_id,
        archived=True,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return ProductMutationResponse(
        product=ProductResponse.model_validate(product),
        message="Product archived successfully.",
    )


@router.post("/{product_id}/restore", response_model=ProductMutationResponse)
async def restore_product(
    product_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductMutationResponse:
    product = await ProductService(session).set_archived(
        product_id,
        archived=False,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return ProductMutationResponse(
        product=ProductResponse.model_validate(product),
        message="Product restored successfully.",
    )
