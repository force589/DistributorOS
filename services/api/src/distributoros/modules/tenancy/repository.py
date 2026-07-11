from typing import cast
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.tenancy.models import Business, Membership


class TenancyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add_business(self, business: Business) -> None:
        self.session.add(business)

    def add_membership(self, membership: Membership) -> None:
        self.session.add(membership)

    async def get_business(self, business_id: UUID) -> Business | None:
        return await self.session.get(Business, business_id)

    async def get_membership(self, user_id: UUID, business_id: UUID) -> Membership | None:
        statement = select(Membership).where(
            Membership.user_id == user_id,
            Membership.business_id == business_id,
        )
        return cast(Membership | None, await self.session.scalar(statement))

    async def get_first_membership(self, user_id: UUID) -> Membership | None:
        statement = (
            select(Membership)
            .where(Membership.user_id == user_id)
            .order_by(Membership.created_at, Membership.business_id)
            .limit(1)
        )
        return cast(Membership | None, await self.session.scalar(statement))

    async def has_financial_history(self, business_id: UUID) -> bool:
        from distributoros.modules.ledger.models import CustomerLedgerEntry

        statement = select(exists().where(CustomerLedgerEntry.tenant_id == business_id))
        return bool(await self.session.scalar(statement))
