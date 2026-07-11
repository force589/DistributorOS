from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.tenancy.models import Business
from distributoros.modules.tenancy.repository import TenancyRepository
from distributoros.modules.tenancy.schemas import BusinessSettingsUpdateRequest


class BusinessSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = TenancyRepository(session)

    async def update(self, business: Business, request: BusinessSettingsUpdateRequest) -> Business:
        changes = request.model_dump(exclude_none=True)
        if (
            request.currency is not None
            and request.currency != business.currency
            and await self.repository.has_financial_history(business.id)
        ):
            raise AppError(
                status_code=409,
                code="CURRENCY_CHANGE_RESTRICTED",
                message=(
                    "Currency cannot be changed after financial transactions exist. "
                    "Keep the current currency to preserve historical amounts."
                ),
                field_errors={
                    "currency": (
                        "This business already has financial history. "
                        "Currency conversion is not supported."
                    )
                },
            )
        for field, value in changes.items():
            setattr(business, field, value)
        await self.session.flush()
        return business
