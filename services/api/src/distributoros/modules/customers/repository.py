from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.customers.models import Customer
from distributoros.modules.customers.schemas import CustomerSort, CustomerStatus


@dataclass(frozen=True)
class CustomerPage:
    items: list[Customer]
    has_more: bool


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_customer_code(self, tenant_id: UUID) -> str:
        number = await self.session.scalar(
            text(
                """
                INSERT INTO customer_code_counters (tenant_id, next_number)
                VALUES (:tenant_id, 2)
                ON CONFLICT (tenant_id) DO UPDATE
                SET next_number = customer_code_counters.next_number + 1
                RETURNING next_number - 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        if number is None:
            raise RuntimeError("Customer code allocation did not return a number.")
        return f"CUST-{int(number):06d}"

    def add(self, customer: Customer) -> None:
        self.session.add(customer)

    async def get(self, tenant_id: UUID, customer_id: UUID) -> Customer | None:
        statement = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id == customer_id,
        )
        return cast(Customer | None, await self.session.scalar(statement))

    async def get_by_code(self, tenant_id: UUID, customer_code: str) -> Customer | None:
        statement = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.customer_code == customer_code.upper(),
        )
        return cast(Customer | None, await self.session.scalar(statement))

    async def list(
        self,
        *,
        tenant_id: UUID,
        customer_status: CustomerStatus,
        customer_sort: CustomerSort,
        search: str | None,
        limit: int,
        cursor_key: str | datetime | None,
        cursor_id: UUID | None,
    ) -> CustomerPage:
        statement = select(Customer).where(Customer.tenant_id == tenant_id)
        if customer_status == "active":
            statement = statement.where(Customer.archived.is_(False))
        elif customer_status == "archived":
            statement = statement.where(Customer.archived.is_(True))

        if search:
            term = search.strip()
            lowered = term.lower()
            statement = statement.where(
                or_(
                    func.lower(Customer.name).contains(lowered, autoescape=True),
                    Customer.phone.contains(term, autoescape=True),
                    func.lower(Customer.email).contains(lowered, autoescape=True),
                    func.lower(Customer.customer_code).contains(lowered, autoescape=True),
                )
            )

        statement = self._apply_cursor_and_order(
            statement,
            customer_sort=customer_sort,
            cursor_key=cursor_key,
            cursor_id=cursor_id,
        ).limit(limit + 1)
        customers = list((await self.session.scalars(statement)).all())
        return CustomerPage(items=customers[:limit], has_more=len(customers) > limit)

    @staticmethod
    def _apply_cursor_and_order(
        statement: Select[tuple[Customer]],
        *,
        customer_sort: CustomerSort,
        cursor_key: str | datetime | None,
        cursor_id: UUID | None,
    ) -> Select[tuple[Customer]]:
        if customer_sort in {"newest", "oldest"}:
            if cursor_key is not None and cursor_id is not None:
                comparison = tuple_(Customer.created_at, Customer.id)
                cursor_tuple = (cursor_key, cursor_id)
                statement = statement.where(
                    comparison < cursor_tuple
                    if customer_sort == "newest"
                    else comparison > cursor_tuple
                )
            order = (
                (Customer.created_at.desc(), Customer.id.desc())
                if customer_sort == "newest"
                else (Customer.created_at.asc(), Customer.id.asc())
            )
            return statement.order_by(*order)

        normalized_name = func.lower(Customer.name)
        if cursor_key is not None and cursor_id is not None:
            comparison = tuple_(normalized_name, Customer.id)
            cursor_tuple = (cursor_key, cursor_id)
            statement = statement.where(
                comparison > cursor_tuple
                if customer_sort == "name_asc"
                else comparison < cursor_tuple
            )
        order = (
            (normalized_name.asc(), Customer.id.asc())
            if customer_sort == "name_asc"
            else (normalized_name.desc(), Customer.id.desc())
        )
        return statement.order_by(*order)
