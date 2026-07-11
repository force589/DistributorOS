from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.identity.models import AuthSession, PasswordResetToken, User


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add_user(self, user: User) -> None:
        self.session.add(user)

    def add_session(self, auth_session: AuthSession) -> None:
        self.session.add(auth_session)

    def add_password_reset_token(self, token: PasswordResetToken) -> None:
        self.session.add(token)

    async def get_user_by_email(self, normalized_email: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(select(User).where(User.email == normalized_email)),
        )

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_session(self, session_id: UUID) -> AuthSession | None:
        return await self.session.get(AuthSession, session_id)

    async def get_session_for_update(self, session_id: UUID) -> AuthSession | None:
        statement = select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        return cast(AuthSession | None, await self.session.scalar(statement))

    async def get_password_reset_token_for_update(
        self, token_id: UUID
    ) -> PasswordResetToken | None:
        statement = (
            select(PasswordResetToken).where(PasswordResetToken.id == token_id).with_for_update()
        )
        return cast(PasswordResetToken | None, await self.session.scalar(statement))

    async def invalidate_password_reset_tokens(self, user_id: UUID, now: datetime) -> None:
        await self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

    async def revoke_all_sessions(self, user_id: UUID, now: datetime) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
