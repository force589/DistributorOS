from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
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
            managed_provider = self._is_managed_postgres(role["is_neon_managed_role"])
            rls_status = (
                await connection.execute(
                    text(
                        """
                        WITH rls_tables AS (
                            SELECT
                                relation.oid,
                                relation.oid::regclass::text AS table_name,
                                relation.relforcerowsecurity,
                                row_security_active(relation.oid::regclass) AS rls_active
                            FROM pg_class relation
                            JOIN pg_namespace namespace
                              ON namespace.oid = relation.relnamespace
                            WHERE namespace.nspname = 'public'
                              AND relation.relkind IN ('r', 'p')
                              AND relation.relrowsecurity
                        )
                        SELECT
                            count(*) AS rls_table_count,
                            count(*) FILTER (
                                WHERE NOT relforcerowsecurity
                            ) AS unforced_rls_table_count,
                            count(*) FILTER (
                                WHERE NOT rls_active
                            ) AS inactive_rls_table_count,
                            coalesce(
                                array_agg(table_name ORDER BY table_name) FILTER (
                                    WHERE NOT relforcerowsecurity
                                ),
                                ARRAY[]::text[]
                            ) AS unforced_rls_tables,
                            coalesce(
                                array_agg(table_name ORDER BY table_name) FILTER (
                                    WHERE NOT rls_active
                                ),
                                ARRAY[]::text[]
                            ) AS inactive_rls_tables
                        FROM rls_tables
                        """
                    )
                )
            ).mappings().one()
            app_table_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pg_class relation
                    JOIN pg_namespace namespace
                      ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname = 'public'
                      AND relation.relkind IN ('r', 'p')
                      AND relation.relname NOT LIKE 'alembic_%'
                    """
                )
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
        if app_table_count and not rls_status["rls_table_count"]:
            raise RuntimeError(
                "No Row Level Security tables were found in the public schema. "
                "Run Alembic migrations before starting the API."
            )
        if rls_status["unforced_rls_table_count"]:
            tables = ", ".join(rls_status["unforced_rls_tables"])
            raise RuntimeError(
                "All public tables with Row Level Security enabled must also use "
                f"FORCE ROW LEVEL SECURITY before starting the API. Missing: {tables}."
            )
        if rls_status["inactive_rls_table_count"]:
            tables = ", ".join(rls_status["inactive_rls_tables"])
            if managed_provider:
                raise RuntimeError(
                    "The managed PostgreSQL runtime role can bypass Row Level Security "
                    f"on migrated application tables: {tables}. Use a role whose effective "
                    "permissions keep row_security_active(...) true for every RLS table."
                )
            raise RuntimeError(
                "The PostgreSQL runtime role can bypass Row Level Security on migrated "
                f"application tables: {tables}. Use a non-superuser, non-BYPASSRLS "
                "application role and keep FORCE ROW LEVEL SECURITY enabled."
            )

    def _is_managed_postgres(self, is_neon_managed_role: bool) -> bool:
        host = self.host.lower()
        return is_neon_managed_role or any(
            host == suffix.removeprefix(".") or host.endswith(suffix)
            for suffix in MANAGED_POSTGRES_HOST_SUFFIXES
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
