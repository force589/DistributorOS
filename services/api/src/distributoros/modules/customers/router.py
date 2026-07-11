from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.modules.customers.schemas import (
    CustomerCreateRequest,
    CustomerListResponse,
    CustomerMutationResponse,
    CustomerResponse,
    CustomerSort,
    CustomerStatus,
    CustomerUpdateRequest,
)
from distributoros.modules.customers.service import CustomerService
from distributoros.modules.identity.dependencies import Principal, get_current_principal

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("", response_model=CustomerMutationResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerMutationResponse:
    customer = await CustomerService(session).create(
        payload,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return CustomerMutationResponse(
        customer=CustomerResponse.model_validate(customer),
        message="Customer created successfully.",
    )


async def _list_customers(
    *,
    principal: Principal,
    session: AsyncSession,
    customer_status: CustomerStatus,
    customer_sort: CustomerSort,
    search: str | None,
    limit: int,
    cursor: str | None,
) -> CustomerListResponse:
    normalized_search = search.strip() if search else None
    page, next_cursor = await CustomerService(session).list(
        tenant_id=principal.business.id,
        customer_status=customer_status,
        customer_sort=customer_sort,
        search=normalized_search or None,
        limit=limit,
        cursor=cursor,
    )
    return CustomerListResponse(
        items=[CustomerResponse.model_validate(customer) for customer in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    customer_status: Annotated[CustomerStatus, Query(alias="status")] = "active",
    customer_sort: Annotated[CustomerSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> CustomerListResponse:
    return await _list_customers(
        principal=principal,
        session=session,
        customer_status=customer_status,
        customer_sort=customer_sort,
        search=search,
        limit=limit,
        cursor=cursor,
    )


@router.get("/search", response_model=CustomerListResponse)
async def search_customers(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str, Query(alias="q", min_length=1, max_length=160)],
    customer_status: Annotated[CustomerStatus, Query(alias="status")] = "active",
    customer_sort: Annotated[CustomerSort, Query(alias="sort")] = "name_asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> CustomerListResponse:
    if not query.strip():
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Enter a customer name, phone number, email, or customer code.",
            field_errors={"q": "Enter a customer name, phone number, email, or customer code."},
        )
    return await _list_customers(
        principal=principal,
        session=session,
        customer_status=customer_status,
        customer_sort=customer_sort,
        search=query,
        limit=limit,
        cursor=cursor,
    )


@router.get("/code/{customer_code}", response_model=CustomerResponse)
async def get_customer_by_code(
    customer_code: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerResponse:
    customer = await CustomerService(session).get_by_code(
        customer_code,
        tenant_id=principal.business.id,
    )
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerResponse:
    customer = await CustomerService(session).get(
        customer_id,
        tenant_id=principal.business.id,
    )
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerMutationResponse)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerMutationResponse:
    customer = await CustomerService(session).update(
        customer_id,
        payload,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return CustomerMutationResponse(
        customer=CustomerResponse.model_validate(customer),
        message="Customer updated successfully.",
    )


@router.post("/{customer_id}/archive", response_model=CustomerMutationResponse)
async def archive_customer(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerMutationResponse:
    customer = await CustomerService(session).set_archived(
        customer_id,
        archived=True,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return CustomerMutationResponse(
        customer=CustomerResponse.model_validate(customer),
        message="Customer archived successfully.",
    )


@router.post("/{customer_id}/restore", response_model=CustomerMutationResponse)
async def restore_customer(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerMutationResponse:
    customer = await CustomerService(session).set_archived(
        customer_id,
        archived=False,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return CustomerMutationResponse(
        customer=CustomerResponse.model_validate(customer),
        message="Customer restored successfully.",
    )
