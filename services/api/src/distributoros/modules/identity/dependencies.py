from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.config import Settings, get_settings
from distributoros.core.database import get_session, set_request_context
from distributoros.core.errors import AppError
from distributoros.modules.identity.models import AuthSession, User
from distributoros.modules.identity.security import decode_access_token
from distributoros.modules.tenancy.models import Business, Membership

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

    await set_request_context(
        session,
        user_id=claims.user_id,
        business_id=claims.business_id,
    )
    row = (
        await session.execute(
            select(AuthSession, Membership, User, Business)
            .join(
                Membership,
                (Membership.business_id == AuthSession.business_id)
                & (Membership.user_id == AuthSession.user_id),
                isouter=True,
            )
            .join(User, User.id == AuthSession.user_id)
            .join(Business, Business.id == AuthSession.business_id)
            .where(
                AuthSession.id == claims.session_id,
                AuthSession.user_id == claims.user_id,
                AuthSession.business_id == claims.business_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
    ).one_or_none()
    if row is None:
        raise _authentication_error()

    auth_session, membership, user, business = row
    if membership is None:
        raise AppError(
            status_code=403,
            code="BUSINESS_ACCESS_REQUIRED",
            message=(
                "Your account no longer has access to this business. "
                "Ask a business owner to restore access."
            ),
        )
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
