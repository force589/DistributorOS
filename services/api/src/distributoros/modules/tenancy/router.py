from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.database import get_session
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.tenancy.models import Business
from distributoros.modules.tenancy.schemas import (
    BusinessSettingsResponse,
    BusinessSettingsUpdateRequest,
)
from distributoros.modules.tenancy.service import BusinessSettingsService

router = APIRouter(prefix="/business", tags=["Business Settings"])


def _response(business: Business) -> BusinessSettingsResponse:
    return BusinessSettingsResponse(
        business_name=business.business_name,
        currency=business.currency,
        language=business.language,
        theme=business.theme,
        timezone=business.timezone,
    )


@router.get("/settings", response_model=BusinessSettingsResponse)
async def get_business_settings(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> BusinessSettingsResponse:
    return _response(principal.business)


@router.patch("/settings", response_model=BusinessSettingsResponse)
async def update_business_settings(
    payload: BusinessSettingsUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BusinessSettingsResponse:
    business = await BusinessSettingsService(session).update(principal.business, payload)
    return _response(business)
