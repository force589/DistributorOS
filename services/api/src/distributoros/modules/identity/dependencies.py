from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.config import Settings, get_settings
from distributoros.core.database import get_session, set_tenant_context, set_user_context
from distributoros.core.errors import AppError
from distributoros.modules.identity.models import AuthSession, User
from distributoros.modules.identity.repository import IdentityRepository
from distributoros.modules.identity.security import decode_access_token
from distributoros.modules.tenancy.models import Business, Membership
from distributoros.modules.tenancy.repository import TenancyRepository

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user: User
    business: Business
    membership: Membership
    auth_session: AuthSession


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()
    try:
        claims = decode_access_token(settings, credentials.credentials)
    except ValueError as exc:
        raise _authentication_error() from exc

    await set_user_context(session, claims.user_id)
    identity = IdentityRepository(session)
    tenancy = TenancyRepository(session)
    auth_session = await identity.get_session(claims.session_id)
    if (
        auth_session is None
        or auth_session.user_id != claims.user_id
        or auth_session.business_id != claims.business_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= datetime.now(UTC)
    ):
        raise _authentication_error()

    membership = await tenancy.get_membership(claims.user_id, claims.business_id)
    if membership is None:
        raise AppError(
            status_code=403,
            code="BUSINESS_ACCESS_REQUIRED",
            message=(
                "Your account no longer has access to this business. "
                "Ask a business owner to restore access."
            ),
        )

    await set_tenant_context(session, claims.business_id)
    user = await identity.get_user(claims.user_id)
    business = await tenancy.get_business(claims.business_id)
    if user is None or business is None:
        raise _authentication_error()
    return Principal(
        user=user,
        business=business,
        membership=membership,
        auth_session=auth_session,
    )


def _authentication_error() -> AppError:
    return AppError(
        status_code=401,
        code="AUTHENTICATION_REQUIRED",
        message="Your session is not valid. Sign in again to continue.",
    )
