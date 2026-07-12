from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

MANAGED_POSTGRES_HOST_SUFFIXES = (
    ".neon.tech",
    ".render.com",
    ".supabase.co",
    ".pooler.supabase.com",
    ".railway.internal",
    ".rlwy.net",
)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.host = make_url(url).host or ""
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
                        SELECT
                            rolsuper,
                            rolbypassrls,
                            EXISTS (
                                SELECT 1
                                FROM pg_roles neon_role
                                WHERE neon_role.rolname = 'neon_superuser'
                                  AND pg_has_role(current_user, neon_role.oid, 'member')
                            ) AS is_neon_managed_role
                        FROM pg_roles
                        WHERE rolname = current_user
                        """
                    )
                )
            ).mappings().one()
            unforced_rls_table_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pg_class relation
                    JOIN pg_namespace namespace
                      ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname = 'public'
                      AND relation.relkind IN ('r', 'p')
                      AND relation.relrowsecurity
                      AND NOT relation.relforcerowsecurity
                    """
                )
            )
            managed_provider = self._is_managed_postgres(role["is_neon_managed_role"])
            rls_probe_passed = (
                await self._runtime_role_enforces_rls(connection)
                if role["rolbypassrls"] and managed_provider
                else True
            )
        if role["rolsuper"]:
            raise RuntimeError(
                "DATABASE_URL must not use a PostgreSQL superuser. "
                "Use an application/database-owner role so Row Level Security "
                "cannot be bypassed."
            )
        if role["rolbypassrls"] and not managed_provider:
            raise RuntimeError(
                "DATABASE_URL must not use a BYPASSRLS role on self-hosted PostgreSQL. "
                "Use a dedicated application role so Row Level Security cannot be bypassed."
            )
        if role["rolbypassrls"] and not rls_probe_passed:
            raise RuntimeError(
                "The managed PostgreSQL role reports BYPASSRLS and an active Row Level "
                "Security probe confirmed that tenant policies can be bypassed. "
                "Use a role without effective BYPASSRLS before starting the API."
            )
        if unforced_rls_table_count:
            raise RuntimeError(
                "All public tables with Row Level Security enabled must also use "
                "FORCE ROW LEVEL SECURITY before starting the API."
            )

    def _is_managed_postgres(self, is_neon_managed_role: bool) -> bool:
        host = self.host.lower()
        return is_neon_managed_role or any(
            host == suffix.removeprefix(".") or host.endswith(suffix)
            for suffix in MANAGED_POSTGRES_HOST_SUFFIXES
        )

    async def _runtime_role_enforces_rls(self, connection: AsyncConnection) -> bool:
        probe_tenant_id = "00000000-0000-0000-0000-000000000001"
        other_tenant_id = "00000000-0000-0000-0000-000000000002"
        await connection.execute(
            text(
                """
                CREATE TEMP TABLE distributoros_rls_probe (
                    tenant_id uuid NOT NULL
                ) ON COMMIT DROP
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO distributoros_rls_probe (tenant_id)
                VALUES (:probe_tenant_id), (:other_tenant_id)
                """
            ),
            {
                "probe_tenant_id": probe_tenant_id,
                "other_tenant_id": other_tenant_id,
            },
        )
        await connection.execute(
            text("ALTER TABLE distributoros_rls_probe ENABLE ROW LEVEL SECURITY")
        )
        await connection.execute(
            text("ALTER TABLE distributoros_rls_probe FORCE ROW LEVEL SECURITY")
        )
        await connection.execute(
            text(
                """
                CREATE POLICY distributoros_rls_probe_tenant
                ON distributoros_rls_probe
                FOR SELECT
                USING (
                    tenant_id =
                    NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                )
                """
            )
        )
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": probe_tenant_id},
        )
        visible_count = await connection.scalar(
            text("SELECT count(*) FROM distributoros_rls_probe")
        )
        await connection.execute(text("DROP TABLE distributoros_rls_probe"))
        return int(visible_count or 0) == 1


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
