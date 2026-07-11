from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.customers.models import Customer
from distributoros.modules.ledger.models import CustomerBalanceProjection
from distributoros.modules.ledger.service import FinancialPostingService
from distributoros.modules.payments.models import Payment, PaymentAllocation
from distributoros.modules.payments.repository import (
    PaymentDetails,
    PaymentPage,
    PaymentsRepository,
)
from distributoros.modules.payments.schemas import (
    CustomerBalanceResponse,
    CustomerCreditResponse,
    PaymentCreateRequest,
    PaymentMethodFilter,
    PaymentSort,
    PaymentStatusFilter,
)


@dataclass(frozen=True)
class ValidatedPaymentAllocation:
    ledger_entry_id: UUID
    invoice_id: UUID | None
    allocated_amount: Decimal


class PaymentsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PaymentsRepository(session)
        self.financial_posting = FinancialPostingService(session)
        self.logger = structlog.get_logger("distributoros.payments")

    async def create(
        self,
        request: PaymentCreateRequest,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> PaymentDetails:
        key = self._idempotency_key(idempotency_key)
        request_hash = self._request_hash(request)
        existing = await self.repository.get_by_create_key(tenant_id, key)
        if existing is not None:
            if existing.create_request_hash != request_hash:
                raise self._idempotency_reused()
            await self.financial_posting.validate_posted_payment(existing)
            return await self.repository.details(tenant_id, existing)
        customer = await self._require_customer(tenant_id, request.customer_id)
        allocations = await self._validate_allocations(
            tenant_id=tenant_id,
            customer_id=customer.id,
            amount=request.amount,
            request=request,
        )
        payment: Payment | None = None
        try:
            async with self.session.begin_nested():
                payment = Payment(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    payment_number=await self.repository.next_payment_number(tenant_id),
                    customer_id=customer.id,
                    payment_date=request.payment_date,
                    amount=request.amount,
                    payment_method=request.payment_method,
                    reference_number=request.reference_number,
                    notes=request.notes,
                    status="POSTED",
                    created_by=user_id,
                    create_idempotency_key=key,
                    create_request_hash=request_hash,
                )
                self.repository.add_payment(payment)
                await self.session.flush()
                self.repository.add_allocations(
                    [
                        PaymentAllocation(
                            id=uuid4(),
                            tenant_id=tenant_id,
                            payment_id=payment.id,
                            ledger_entry_id=allocation.ledger_entry_id,
                            invoice_id=allocation.invoice_id,
                            allocated_amount=allocation.allocated_amount,
                        )
                        for allocation in allocations
                    ]
                )
                await self.session.flush()
                await self.financial_posting.post_payment(payment, user_id=user_id)
                await self.session.flush()
        except IntegrityError as exc:
            constraint = _constraint_name(exc)
            if constraint == "uq_payments_tenant_create_idempotency":
                existing = await self.repository.get_by_create_key(tenant_id, key)
                if existing is None:
                    raise
                if existing.create_request_hash != request_hash:
                    raise self._idempotency_reused() from exc
                await self.financial_posting.validate_posted_payment(existing)
                return await self.repository.details(tenant_id, existing)
            if constraint == "uq_payments_tenant_payment_number":
                raise AppError(
                    status_code=409,
                    code="PAYMENT_NUMBER_ALREADY_EXISTS",
                    message=(
                        "A payment with this number already exists. Refresh payments and try again."
                    ),
                ) from exc
            raise
        if payment is None:
            raise RuntimeError("Payment creation did not produce a payment.")
        details = await self.repository.details(tenant_id, payment)
        self.logger.info(
            "payment_posted",
            tenant_id=str(tenant_id),
            payment_id=str(payment.id),
            payment_number=payment.payment_number,
            user_id=str(user_id),
        )
        return details

    async def get(self, payment_id: UUID, *, tenant_id: UUID) -> PaymentDetails:
        payment = self._require_payment(await self.repository.get(tenant_id, payment_id))
        return await self.repository.details(tenant_id, payment)

    async def get_by_number(self, payment_number: str, *, tenant_id: UUID) -> PaymentDetails:
        payment = self._require_payment(
            await self.repository.get_by_number(tenant_id, payment_number)
        )
        return await self.repository.details(tenant_id, payment)

    async def void(
        self,
        payment_id: UUID,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> PaymentDetails:
        key = self._idempotency_key(idempotency_key)
        try:
            async with self.session.begin_nested():
                details = await self._void_once(
                    payment_id,
                    key=key,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_payments_tenant_void_idempotency":
                raise self._idempotency_reused() from exc
            raise
        return details

    async def _void_once(
        self,
        payment_id: UUID,
        *,
        key: str,
        tenant_id: UUID,
        user_id: UUID,
    ) -> PaymentDetails:
        payment = self._require_payment(await self.repository.get_for_update(tenant_id, payment_id))
        if payment.status == "VOID":
            if payment.void_idempotency_key == key:
                await self.financial_posting.validate_voided_payment(payment)
                return await self.repository.details(tenant_id, payment)
            raise AppError(
                status_code=409,
                code="PAYMENT_ALREADY_VOIDED",
                message="This payment has already been voided.",
            )
        await self.financial_posting.validate_can_void_payment(payment)
        await self.financial_posting.void_payment(payment, user_id=user_id)
        payment.status = "VOID"
        payment.void_idempotency_key = key
        await self.session.flush()
        details = await self.repository.details(tenant_id, payment)
        self.logger.info(
            "payment_voided",
            tenant_id=str(tenant_id),
            payment_id=str(payment.id),
            payment_number=payment.payment_number,
            user_id=str(user_id),
        )
        return details

    async def list_payments(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID | None,
        payment_status: PaymentStatusFilter,
        payment_method: PaymentMethodFilter,
        payment_sort: PaymentSort,
        search: str | None,
        payment_date: date | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[PaymentPage, str | None]:
        if customer_id is not None:
            await self._require_customer_exists(tenant_id, customer_id)
        cursor_created, cursor_id = self._decode_cursor(
            cursor,
            customer_id=customer_id,
            payment_status=payment_status,
            payment_method=payment_method,
            payment_sort=payment_sort,
            search=search,
            payment_date=payment_date,
        )
        page = await self.repository.list_payments(
            tenant_id=tenant_id,
            customer_id=customer_id,
            payment_status=payment_status,
            payment_method=payment_method,
            payment_sort=payment_sort,
            search=search,
            payment_date=payment_date,
            limit=limit,
            cursor_created_at=cursor_created,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1].payment
            next_cursor = self._encode_cursor(
                created_at=last.created_at,
                payment_id=last.id,
                customer_id=customer_id,
                payment_status=payment_status,
                payment_method=payment_method,
                payment_sort=payment_sort,
                search=search,
                payment_date=payment_date,
            )
        return page, next_cursor

    async def credit(self, *, tenant_id: UUID, customer_id: UUID) -> CustomerCreditResponse:
        projection = await self._customer_projection(tenant_id, customer_id)
        return CustomerCreditResponse(
            customer_id=customer_id,
            available_credit=projection.available_credit if projection else Decimal("0.00"),
        )

    async def balance(self, *, tenant_id: UUID, customer_id: UUID) -> CustomerBalanceResponse:
        projection = await self._customer_projection(tenant_id, customer_id)
        return CustomerBalanceResponse(
            customer_id=customer_id,
            outstanding_balance=(projection.outstanding_balance if projection else Decimal("0.00")),
            available_credit=projection.available_credit if projection else Decimal("0.00"),
            total_sales=projection.total_sales if projection else Decimal("0.00"),
            total_payments=projection.total_payments if projection else Decimal("0.00"),
            last_sale_date=projection.last_sale_at if projection else None,
            last_payment_date=projection.last_payment_at if projection else None,
        )

    async def _customer_projection(
        self, tenant_id: UUID, customer_id: UUID
    ) -> CustomerBalanceProjection | None:
        await self._require_customer_exists(tenant_id, customer_id)
        projection = await self.financial_posting.repository.get_projection(tenant_id, customer_id)
        if projection is None and await self.financial_posting.repository.has_customer_entries(
            tenant_id, customer_id
        ):
            raise FinancialPostingService._corrupt_state()
        return projection

    async def _validate_allocations(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        amount: Decimal,
        request: PaymentCreateRequest,
    ) -> list[ValidatedPaymentAllocation]:
        if not request.allocations:
            return []
        target_keys = [
            (
                "invoice",
                allocation.invoice_id,
            )
            if allocation.invoice_id is not None
            else ("ledger", allocation.ledger_entry_id)
            for allocation in request.allocations
        ]
        if len(target_keys) != len(set(target_keys)):
            raise AppError(
                status_code=422,
                code="DUPLICATE_PAYMENT_ALLOCATION",
                message="Each invoice or ledger entry can be allocated only once in a payment.",
                field_errors={"allocations": "Remove duplicate allocation targets and try again."},
            )
        total = sum(
            (allocation.allocated_amount for allocation in request.allocations),
            Decimal("0.00"),
        )
        if total > amount:
            raise AppError(
                status_code=422,
                code="PAYMENT_ALLOCATION_TOTAL_INVALID",
                message="Allocated amount cannot be greater than the payment amount.",
                field_errors={
                    "allocations": "Reduce allocations so they do not exceed the payment amount."
                },
            )
        ledger_ids = {
            allocation.ledger_entry_id
            for allocation in request.allocations
            if allocation.ledger_entry_id is not None
        }
        invoice_ids = {
            allocation.invoice_id
            for allocation in request.allocations
            if allocation.invoice_id is not None
        }
        targets = await self.repository.allocation_targets(
            tenant_id=tenant_id,
            customer_id=customer_id,
            entry_ids=ledger_ids,
        )
        invoice_targets = await self.repository.invoice_allocation_targets(
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_ids=invoice_ids,
        )
        missing = (ledger_ids - targets.keys()) or (invoice_ids - invoice_targets.keys())
        if missing:
            raise AppError(
                status_code=404,
                code="PAYMENT_ALLOCATION_TARGET_NOT_FOUND",
                message="One allocation target was not found or is not issued for this customer.",
                field_errors={
                    "allocations": (
                        "Select issued invoices or open ledger entries from this customer."
                    )
                },
            )
        projection = await self.financial_posting.repository.get_projection(
            tenant_id, customer_id, for_update=True
        )
        if projection is None:
            raise FinancialPostingService._corrupt_state()
        targets = await self.repository.allocation_targets(
            tenant_id=tenant_id,
            customer_id=customer_id,
            entry_ids=ledger_ids,
        )
        invoice_targets = await self.repository.invoice_allocation_targets(
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_ids=invoice_ids,
        )
        missing = (ledger_ids - targets.keys()) or (invoice_ids - invoice_targets.keys())
        if missing:
            raise AppError(
                status_code=404,
                code="PAYMENT_ALLOCATION_TARGET_NOT_FOUND",
                message="One allocation target was not found or is not issued for this customer.",
                field_errors={
                    "allocations": (
                        "Select issued invoices or open ledger entries from this customer."
                    )
                },
            )
        validated: list[ValidatedPaymentAllocation] = []
        for index, allocation in enumerate(request.allocations):
            if allocation.invoice_id is not None:
                invoice_target = invoice_targets[allocation.invoice_id]
                if allocation.allocated_amount > invoice_target.remaining_amount:
                    raise AppError(
                        status_code=422,
                        code="PAYMENT_ALLOCATION_AMOUNT_INVALID",
                        message=(
                            f"Only {_money_text(invoice_target.remaining_amount)} is open for "
                            f"{invoice_target.reference}."
                        ),
                        field_errors={
                            f"allocations.{index}.allocated_amount": (
                                "Reduce the allocation amount and try again."
                            )
                        },
                    )
                validated.append(
                    ValidatedPaymentAllocation(
                        ledger_entry_id=invoice_target.entry.id,
                        invoice_id=invoice_target.invoice.id,
                        allocated_amount=allocation.allocated_amount,
                    )
                )
                continue
            if allocation.ledger_entry_id is None:
                raise AppError(
                    status_code=422,
                    code="PAYMENT_ALLOCATION_TARGET_REQUIRED",
                    message="Select an invoice or ledger entry for each allocation.",
                    field_errors={f"allocations.{index}": "Select an invoice or ledger entry."},
                )
            target = targets[allocation.ledger_entry_id]
            if allocation.allocated_amount > target.remaining_amount:
                raise AppError(
                    status_code=422,
                    code="PAYMENT_ALLOCATION_AMOUNT_INVALID",
                    message=(
                        f"Only {_money_text(target.remaining_amount)} is open for "
                        f"{target.reference}."
                    ),
                    field_errors={
                        f"allocations.{index}.allocated_amount": (
                            "Reduce the allocation amount and try again."
                        )
                    },
                )
            validated.append(
                ValidatedPaymentAllocation(
                    ledger_entry_id=target.entry.id,
                    invoice_id=None,
                    allocated_amount=allocation.allocated_amount,
                )
            )
        return validated

    async def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        customer = await self.repository.get_customer(tenant_id, customer_id)
        if customer is None:
            raise AppError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="Customer not found.",
                field_errors={"customer_id": "Select a customer from this business."},
            )
        if customer.archived:
            raise AppError(
                status_code=422,
                code="CUSTOMER_ARCHIVED",
                message=(
                    "Customer has been archived. Restore the customer before recording a payment."
                ),
                field_errors={"customer_id": "Customer has been archived."},
            )
        return customer

    async def _require_customer_exists(self, tenant_id: UUID, customer_id: UUID) -> None:
        if await self.repository.get_customer(tenant_id, customer_id) is None:
            raise AppError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="Customer not found.",
            )

    @staticmethod
    def _require_payment(payment: Payment | None) -> Payment:
        if payment is None:
            raise AppError(
                status_code=404,
                code="PAYMENT_NOT_FOUND",
                message="This payment was not found. Refresh payments and try again.",
            )
        return payment

    @staticmethod
    def _idempotency_key(value: str | None) -> str:
        if value is None or not value.strip():
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_REQUIRED",
                message="A submission key is required. Submit the payment again.",
                field_errors={"idempotency_key": "Submit again to generate a new key."},
            )
        key = value.strip()
        if len(key) > 128:
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_INVALID",
                message="The submission key is too long. Submit the payment again.",
                field_errors={"idempotency_key": "Submission key is too long."},
            )
        return key

    @staticmethod
    def _request_hash(request: PaymentCreateRequest) -> str:
        allocations = sorted(
            (
                {
                    "ledger_entry_id": str(allocation.ledger_entry_id),
                    "invoice_id": str(allocation.invoice_id) if allocation.invoice_id else "",
                    "allocated_amount": str(allocation.allocated_amount),
                }
                for allocation in request.allocations
            ),
            key=lambda item: (item["invoice_id"], item["ledger_entry_id"]),
        )
        raw = json.dumps(
            {
                "customer_id": str(request.customer_id),
                "payment_date": request.payment_date.isoformat(),
                "amount": str(request.amount),
                "payment_method": request.payment_method,
                "reference_number": request.reference_number or "",
                "notes": request.notes or "",
                "allocations": allocations,
            },
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
                "This submission key was already used for a different payment operation. "
                "Submit again to generate a new key."
            ),
            field_errors={"idempotency_key": "Use a new submission key and try again."},
        )

    @staticmethod
    def _fingerprint(
        *,
        customer_id: UUID | None,
        payment_status: PaymentStatusFilter,
        payment_method: PaymentMethodFilter,
        payment_sort: PaymentSort,
        search: str | None,
        payment_date: date | None,
    ) -> str:
        raw = json.dumps(
            {
                "customer_id": str(customer_id) if customer_id else "",
                "status": payment_status,
                "method": payment_method,
                "sort": payment_sort,
                "search": (search or "").strip().lower(),
                "date": payment_date.isoformat() if payment_date else "",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def _encode_cursor(
        cls,
        *,
        created_at: datetime,
        payment_id: UUID,
        customer_id: UUID | None,
        payment_status: PaymentStatusFilter,
        payment_method: PaymentMethodFilter,
        payment_sort: PaymentSort,
        search: str | None,
        payment_date: date | None,
    ) -> str:
        payload = {
            "v": 1,
            "created_at": created_at.isoformat(),
            "id": str(payment_id),
            "fingerprint": cls._fingerprint(
                customer_id=customer_id,
                payment_status=payment_status,
                payment_method=payment_method,
                payment_sort=payment_sort,
                search=search,
                payment_date=payment_date,
            ),
        }
        return (
            base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    @classmethod
    def _decode_cursor(
        cls,
        cursor: str | None,
        *,
        customer_id: UUID | None,
        payment_status: PaymentStatusFilter,
        payment_method: PaymentMethodFilter,
        payment_sort: PaymentSort,
        search: str | None,
        payment_date: date | None,
    ) -> tuple[datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(padded)))
            if payload.get("v") != 1 or payload.get("fingerprint") != cls._fingerprint(
                customer_id=customer_id,
                payment_status=payment_status,
                payment_method=payment_method,
                payment_sort=payment_sort,
                search=search,
                payment_date=payment_date,
            ):
                raise ValueError
            return datetime.fromisoformat(str(payload["created_at"])), UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_PAYMENT_CURSOR",
                message="This payments page is no longer valid. Refresh the list and try again.",
                field_errors={"cursor": "Refresh the payments list before loading more."},
            ) from exc


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _constraint_name(exc: IntegrityError) -> str | None:
    current: BaseException | None = exc.orig
    while current is not None:
        constraint = cast(str | None, getattr(current, "constraint_name", None))
        if constraint:
            return constraint
        current = current.__cause__
    return None
