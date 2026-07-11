from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def validate_runtime_role_supports_rls(self) -> None:
        async with self.engine.connect() as connection:
            role = (
                await connection.execute(
                    text(
                        """
                        SELECT rolsuper, rolbypassrls
                        FROM pg_roles
                        WHERE rolname = current_user
                        """
                    )
                )
            ).mappings().one()
        if role["rolsuper"] or role["rolbypassrls"]:
            raise RuntimeError(
                "DATABASE_URL must not use a PostgreSQL superuser or BYPASSRLS role. "
                "Use the managed database owner/application role so Row Level Security "
                "cannot be bypassed."
            )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database
    async with database.session_factory() as session, session.begin():
        yield session


async def set_user_context(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def set_tenant_context(session: AsyncSession, business_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :business_id, true)"),
        {"business_id": str(business_id)},
    )


async def set_internal_maintenance_context(connection: Any) -> None:
    await connection.execute(
        text("SELECT set_config('app.internal_maintenance', 'true', true)")
    )
