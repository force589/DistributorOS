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
    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 3,
        max_overflow: int = 2,
        pool_recycle_seconds: int = 1800,
    ) -> None:
        self.url = url
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle_seconds,
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
                            rolbypassrls
                        FROM pg_roles
                        WHERE rolname = current_user
                        """
                    )
                )
            ).mappings().one()
            rls_status = (
                await connection.execute(
                    text(
                        """
                        WITH rls_tables AS (
                            SELECT
                                relation.oid,
                                relation.oid::regclass::text AS table_name,
                                relation.relforcerowsecurity,
                                pg_get_userbyid(relation.relowner) = current_user
                                  AS runtime_role_owns_table,
                                row_security_active(relation.oid::regclass) AS rls_active,
                                EXISTS (
                                    SELECT 1
                                    FROM pg_policy policy
                                    WHERE policy.polrelid = relation.oid
                                ) AS has_policy
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
                                WHERE NOT has_policy
                            ) AS policyless_rls_table_count,
                            count(*) FILTER (
                                WHERE runtime_role_owns_table
                            ) AS runtime_owned_rls_table_count,
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
                                    WHERE NOT has_policy
                                ),
                                ARRAY[]::text[]
                            ) AS policyless_rls_tables,
                            coalesce(
                                array_agg(table_name ORDER BY table_name) FILTER (
                                    WHERE runtime_role_owns_table
                                ),
                                ARRAY[]::text[]
                            ) AS runtime_owned_rls_tables,
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
        if role["rolbypassrls"]:
            raise RuntimeError(
                "DATABASE_URL must not use a BYPASSRLS role. Use a dedicated "
                "non-BYPASSRLS application role so Row Level Security cannot be bypassed. "
                "On managed PostgreSQL providers such as Neon, use the provider owner/admin "
                "role only for DATABASE_ADMIN_URL and migrations, then create a SQL-managed "
                "runtime role with ordinary table privileges for DATABASE_URL."
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
        if rls_status["policyless_rls_table_count"]:
            tables = ", ".join(rls_status["policyless_rls_tables"])
            raise RuntimeError(
                "Every public Row Level Security table must have at least one policy "
                f"before starting the API. Missing policies: {tables}."
            )
        if rls_status["runtime_owned_rls_table_count"]:
            tables = ", ".join(rls_status["runtime_owned_rls_tables"])
            raise RuntimeError(
                "DATABASE_URL must not use the owner of RLS-protected application "
                f"tables: {tables}. Use a separate migration role for schema ownership "
                "and a least-privilege runtime role for the API."
            )
        if rls_status["inactive_rls_table_count"]:
            tables = ", ".join(rls_status["inactive_rls_tables"])
            raise RuntimeError(
                "The PostgreSQL runtime role can bypass Row Level Security on migrated "
                f"application tables: {tables}. Use a non-superuser, non-BYPASSRLS "
                "application role and keep FORCE ROW LEVEL SECURITY enabled."
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


async def set_request_context(session: AsyncSession, *, user_id: UUID, business_id: UUID) -> None:
    await session.execute(
        text(
            """
            SELECT
                set_config('app.current_user_id', :user_id, true),
                set_config('app.current_tenant_id', :business_id, true)
            """
        ),
        {"user_id": str(user_id), "business_id": str(business_id)},
    )


async def set_internal_maintenance_context(connection: Any) -> None:
    await connection.execute(
        text("SELECT set_config('app.internal_maintenance', 'true', true)")
    )
