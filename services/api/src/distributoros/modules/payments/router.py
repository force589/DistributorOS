from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.payments.repository import PaymentDetails, PaymentListRow
from distributoros.modules.payments.schemas import (
    CustomerBalanceResponse,
    CustomerCreditResponse,
    PaymentAllocationResponse,
    PaymentCreateRequest,
    PaymentListItemResponse,
    PaymentListResponse,
    PaymentMethodFilter,
    PaymentMutationResponse,
    PaymentResponse,
    PaymentSort,
    PaymentStatusFilter,
)
from distributoros.modules.payments.service import PaymentsService

router = APIRouter(tags=["Payments"])


def _allocation_response(details: PaymentDetails) -> list[PaymentAllocationResponse]:
    return [
        PaymentAllocationResponse(
            id=item.allocation.id,
            ledger_entry_id=item.allocation.ledger_entry_id,
            invoice_id=item.allocation.invoice_id,
            reference_type=item.reference_type,
            reference=item.reference,
            allocated_amount=item.allocation.allocated_amount,
            created_at=item.allocation.created_at,
        )
        for item in details.allocations
    ]


def _payment_response(details: PaymentDetails) -> PaymentResponse:
    payment = details.payment
    unallocated = payment.amount - details.allocated_amount
    return PaymentResponse(
        id=payment.id,
        payment_number=payment.payment_number,
        customer_id=payment.customer_id,
        customer_name=details.customer_name,
        payment_date=payment.payment_date,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference_number=payment.reference_number,
        notes=payment.notes,
        status=payment.status,
        created_at=payment.created_at,
        created_by=payment.created_by,
        allocated_amount=details.allocated_amount,
        unallocated_amount=unallocated if unallocated > 0 else Decimal("0.00"),
        allocations=_allocation_response(details),
    )


def _list_item(row: PaymentListRow) -> PaymentListItemResponse:
    payment = row.payment
    unallocated = payment.amount - row.allocated_amount
    return PaymentListItemResponse(
        id=payment.id,
        payment_number=payment.payment_number,
        customer_id=payment.customer_id,
        customer_name=row.customer_name,
        payment_date=payment.payment_date,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference_number=payment.reference_number,
        status=payment.status,
        created_at=payment.created_at,
        allocated_amount=row.allocated_amount,
        unallocated_amount=unallocated if unallocated > 0 else Decimal("0.00"),
    )


@router.post(
    "/payments",
    response_model=PaymentMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    payload: PaymentCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PaymentMutationResponse:
    details = await PaymentsService(session).create(
        payload,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return PaymentMutationResponse(
        payment=_payment_response(details),
        message="Payment recorded successfully.",
    )


async def _list_payments(
    *,
    principal: Principal,
    session: AsyncSession,
    customer_id: UUID | None,
    payment_status: PaymentStatusFilter,
    payment_method: PaymentMethodFilter,
    payment_sort: PaymentSort,
    search: str | None,
    payment_date: date | None,
    limit: int,
    cursor: str | None,
) -> PaymentListResponse:
    page, next_cursor = await PaymentsService(session).list_payments(
        tenant_id=principal.business.id,
        customer_id=customer_id,
        payment_status=payment_status,
        payment_method=payment_method,
        payment_sort=payment_sort,
        search=search.strip() if search and search.strip() else None,
        payment_date=payment_date,
        limit=limit,
        cursor=cursor,
    )
    return PaymentListResponse(
        items=[_list_item(row) for row in page.items],
        next_cursor=next_cursor,
        has_more=page.has_more,
        page_size=len(page.items),
    )


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payment_status: Annotated[PaymentStatusFilter, Query(alias="status")] = "all",
    payment_method: Annotated[PaymentMethodFilter, Query(alias="method")] = "all",
    payment_sort: Annotated[PaymentSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    payment_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> PaymentListResponse:
    return await _list_payments(
        principal=principal,
        session=session,
        customer_id=None,
        payment_status=payment_status,
        payment_method=payment_method,
        payment_sort=payment_sort,
        search=search,
        payment_date=payment_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/payments/search", response_model=PaymentListResponse)
async def search_payments(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    query: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    payment_status: Annotated[PaymentStatusFilter, Query(alias="status")] = "all",
    payment_method: Annotated[PaymentMethodFilter, Query(alias="method")] = "all",
    payment_sort: Annotated[PaymentSort, Query(alias="sort")] = "newest",
    payment_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> PaymentListResponse:
    if (
        not (query and query.strip())
        and payment_status == "all"
        and payment_method == "all"
        and payment_date is None
    ):
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Enter a payment number, reference, customer, method, date, or status.",
            field_errors={"q": "Enter a payment number, reference, or customer."},
        )
    return await _list_payments(
        principal=principal,
        session=session,
        customer_id=None,
        payment_status=payment_status,
        payment_method=payment_method,
        payment_sort=payment_sort,
        search=query,
        payment_date=payment_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/payments/number/{payment_number}", response_model=PaymentResponse)
async def get_payment_by_number(
    payment_number: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentResponse:
    return _payment_response(
        await PaymentsService(session).get_by_number(
            payment_number,
            tenant_id=principal.business.id,
        )
    )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentResponse:
    return _payment_response(
        await PaymentsService(session).get(
            payment_id,
            tenant_id=principal.business.id,
        )
    )


@router.post("/payments/{payment_id}/void", response_model=PaymentMutationResponse)
async def void_payment(
    payment_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PaymentMutationResponse:
    details = await PaymentsService(session).void(
        payment_id,
        idempotency_key=idempotency_key,
        tenant_id=principal.business.id,
        user_id=principal.user.id,
    )
    return PaymentMutationResponse(
        payment=_payment_response(details),
        message="Payment voided successfully.",
    )


@router.get("/customers/{customer_id}/payments", response_model=PaymentListResponse)
async def list_customer_payments(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payment_status: Annotated[PaymentStatusFilter, Query(alias="status")] = "all",
    payment_method: Annotated[PaymentMethodFilter, Query(alias="method")] = "all",
    payment_sort: Annotated[PaymentSort, Query(alias="sort")] = "newest",
    search: Annotated[str | None, Query(max_length=160)] = None,
    payment_date: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
) -> PaymentListResponse:
    return await _list_payments(
        principal=principal,
        session=session,
        customer_id=customer_id,
        payment_status=payment_status,
        payment_method=payment_method,
        payment_sort=payment_sort,
        search=search,
        payment_date=payment_date,
        limit=limit,
        cursor=cursor,
    )


@router.get("/customers/{customer_id}/credit", response_model=CustomerCreditResponse)
async def get_customer_credit(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerCreditResponse:
    return await PaymentsService(session).credit(
        tenant_id=principal.business.id,
        customer_id=customer_id,
    )


@router.get("/customers/{customer_id}/balance", response_model=CustomerBalanceResponse)
async def get_customer_balance(
    customer_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerBalanceResponse:
    return await PaymentsService(session).balance(
        tenant_id=principal.business.id,
        customer_id=customer_id,
    )
