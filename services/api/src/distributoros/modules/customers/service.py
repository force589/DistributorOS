import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.customers.models import Customer
from distributoros.modules.customers.repository import CustomerPage, CustomerRepository
from distributoros.modules.customers.schemas import (
    CustomerCreateRequest,
    CustomerSort,
    CustomerStatus,
    CustomerUpdateRequest,
)


class CustomerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CustomerRepository(session)
        self.logger = structlog.get_logger("distributoros.customers")

    async def create(
        self, request: CustomerCreateRequest, *, tenant_id: UUID, user_id: UUID
    ) -> Customer:
        customer = Customer(
            id=uuid4(),
            tenant_id=tenant_id,
            customer_code=await self.repository.next_customer_code(tenant_id),
            created_by=user_id,
            updated_by=user_id,
            **request.model_dump(),
        )
        self.repository.add(customer)
        await self._flush_with_duplicate_name(customer.name)
        self.logger.info(
            "customer_created",
            tenant_id=str(tenant_id),
            customer_id=str(customer.id),
            customer_code=customer.customer_code,
            user_id=str(user_id),
        )
        return customer

    async def get(self, customer_id: UUID, *, tenant_id: UUID) -> Customer:
        customer = await self.repository.get(tenant_id, customer_id)
        return self._require_customer(customer)

    async def get_by_code(self, customer_code: str, *, tenant_id: UUID) -> Customer:
        customer = await self.repository.get_by_code(tenant_id, customer_code)
        return self._require_customer(customer)

    async def update(
        self,
        customer_id: UUID,
        request: CustomerUpdateRequest,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Customer:
        customer = await self.get(customer_id, tenant_id=tenant_id)
        changes = request.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(customer, field, value)
        customer.updated_by = user_id
        customer.updated_at = datetime.now(UTC)
        await self._flush_with_duplicate_name(customer.name)
        self.logger.info(
            "customer_updated",
            tenant_id=str(tenant_id),
            customer_id=str(customer.id),
            user_id=str(user_id),
        )
        return customer

    async def set_archived(
        self,
        customer_id: UUID,
        *,
        archived: bool,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Customer:
        customer = await self.get(customer_id, tenant_id=tenant_id)
        if customer.archived != archived:
            customer.archived = archived
            customer.updated_by = user_id
            customer.updated_at = datetime.now(UTC)
            await self.session.flush()
        self.logger.info(
            "customer_archived" if archived else "customer_restored",
            tenant_id=str(tenant_id),
            customer_id=str(customer.id),
            user_id=str(user_id),
        )
        return customer

    async def list(
        self,
        *,
        tenant_id: UUID,
        customer_status: CustomerStatus,
        customer_sort: CustomerSort,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[CustomerPage, str | None]:
        cursor_key, cursor_id = self._decode_cursor(
            cursor,
            customer_sort=customer_sort,
            customer_status=customer_status,
            search=search,
        )
        page = await self.repository.list(
            tenant_id=tenant_id,
            customer_status=customer_status,
            customer_sort=customer_sort,
            search=search,
            limit=limit,
            cursor_key=cursor_key,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1]
            key: str
            if customer_sort in {"newest", "oldest"}:
                key = last.created_at.isoformat()
            else:
                key = last.name.lower()
            next_cursor = self._encode_cursor(
                key=key,
                customer_id=last.id,
                customer_sort=customer_sort,
                customer_status=customer_status,
                search=search,
            )
        return page, next_cursor

    async def _flush_with_duplicate_name(self, name: str) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if _is_duplicate_customer_name(exc):
                raise AppError(
                    status_code=409,
                    code="CUSTOMER_NAME_ALREADY_EXISTS",
                    message="A customer with this name already exists.",
                    field_errors={"name": "A customer with this name already exists."},
                ) from exc
            raise

    @staticmethod
    def _require_customer(customer: Customer | None) -> Customer:
        if customer is None:
            raise AppError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="This customer was not found. Refresh the customer list and try again.",
            )
        return customer

    @staticmethod
    def _fingerprint(
        *, customer_sort: CustomerSort, customer_status: CustomerStatus, search: str | None
    ) -> str:
        value = json.dumps(
            {
                "sort": customer_sort,
                "status": customer_status,
                "search": (search or "").strip().lower(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    @classmethod
    def _encode_cursor(
        cls,
        *,
        key: str,
        customer_id: UUID,
        customer_sort: CustomerSort,
        customer_status: CustomerStatus,
        search: str | None,
    ) -> str:
        payload = {
            "v": 1,
            "key": key,
            "id": str(customer_id),
            "fingerprint": cls._fingerprint(
                customer_sort=customer_sort,
                customer_status=customer_status,
                search=search,
            ),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def _decode_cursor(
        cls,
        cursor: str | None,
        *,
        customer_sort: CustomerSort,
        customer_status: CustomerStatus,
        search: str | None,
    ) -> tuple[str | datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
            if payload.get("v") != 1 or payload.get("fingerprint") != cls._fingerprint(
                customer_sort=customer_sort,
                customer_status=customer_status,
                search=search,
            ):
                raise ValueError
            customer_id = UUID(str(payload["id"]))
            raw_key = str(payload["key"])
            key: str | datetime = (
                datetime.fromisoformat(raw_key)
                if customer_sort in {"newest", "oldest"}
                else raw_key
            )
            return key, customer_id
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_CUSTOMER_CURSOR",
                message=(
                    "This customer list page is no longer valid. Refresh the list and try again."
                ),
                field_errors={"cursor": "Refresh the customer list before loading more."},
            ) from exc


def _is_duplicate_customer_name(exc: IntegrityError) -> bool:
    current: BaseException | None = exc.orig
    while current is not None:
        if (
            getattr(current, "sqlstate", None) == "23505"
            and getattr(current, "constraint_name", None) == "uq_customers_tenant_name_ci"
        ):
            return True
        current = current.__cause__
    return False
