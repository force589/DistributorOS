import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings, get_settings
from distributoros.core.database import set_internal_maintenance_context

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://distributoros_test_runtime:test-runtime-password@localhost:5432/"
    "distributoros_test_managed",
)
TEST_DATABASE_ADMIN_URL = os.getenv(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+asyncpg://distributoros_test_migrator:test-migrator-password@localhost:5432/"
    "distributoros_test_managed",
)
TEST_DATABASE_BOOTSTRAP_URL = os.getenv(
    "TEST_DATABASE_BOOTSTRAP_URL",
    "postgresql+asyncpg://distributoros_admin:test-admin-password@localhost:5432/postgres",
)
BOOTSTRAP_MANAGED_TEST_DATABASE = "TEST_DATABASE_URL" not in os.environ
TEST_JWT_SECRET = "phase-1-test-secret-that-is-longer-than-thirty-two-characters"

ROOT_TABLES = (
    "outbox_events",
    "request_rate_limits",
    "password_reset_tokens",
    "auth_sessions",
    "memberships",
    "users",
    "businesses",
)

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("DATABASE_MIGRATION_URL", TEST_DATABASE_ADMIN_URL)
os.environ.setdefault("DATABASE_ADMIN_URL", TEST_DATABASE_ADMIN_URL)
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)

from distributoros.main import create_app  # noqa: E402


def _quote_identifier(identifier: str) -> str:
    if not identifier or "\x00" in identifier:
        raise ValueError("Invalid PostgreSQL identifier.")
    return '"' + identifier.replace('"', '""') + '"'


def _asyncpg_kwargs(url: str) -> dict[str, object]:
    parsed = make_url(url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.host or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.database,
    }


async def _ensure_managed_test_database(
    bootstrap_url: str,
    migration_url: str,
    runtime_url: str,
) -> None:
    """Create local non-superuser migration/runtime roles for RLS regression tests.

    PostgreSQL Docker's POSTGRES_USER is a superuser and therefore bypasses RLS.
    Managed providers such as Neon, Render PostgreSQL, Supabase, and Railway expose
    non-superuser owner/application roles. The regression suite must run with a
    managed-provider shape where migrations own schema objects and the API uses a
    separate runtime role so direct RLS assertions are meaningful.
    """

    migration = make_url(migration_url)
    runtime = make_url(runtime_url)
    if migration.username is None or migration.password is None or migration.database is None:
        raise ValueError("TEST_DATABASE_ADMIN_URL must include user, password, and database.")
    if runtime.username is None or runtime.password is None or runtime.database is None:
        raise ValueError("TEST_DATABASE_URL must include user, password, and database.")
    if migration.database != runtime.database:
        raise ValueError("TEST_DATABASE_ADMIN_URL and TEST_DATABASE_URL must target the same DB.")
    migration_role = _quote_identifier(migration.username)
    runtime_role = _quote_identifier(runtime.username)
    database_name = _quote_identifier(runtime.database)
    conn = await asyncpg.connect(**_asyncpg_kwargs(bootstrap_url))
    try:
        for role in (migration, runtime):
            assert role.username is not None
            assert role.password is not None
            password_literal = await conn.fetchval("SELECT quote_literal($1)", role.password)
            quoted_role = _quote_identifier(role.username)
            role_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $1)",
                role.username,
            )
            if not role_exists:
                await conn.execute(
                    "CREATE ROLE "
                    f"{quoted_role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {password_literal}",
                )
            else:
                await conn.execute(
                    "ALTER ROLE "
                    f"{quoted_role} WITH LOGIN NOSUPERUSER NOBYPASSRLS "
                    f"PASSWORD {password_literal}",
                )
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1",
            runtime.database,
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {database_name}")
        await conn.execute(f"CREATE DATABASE {database_name} OWNER {migration_role}")
        await conn.execute(f"GRANT CONNECT ON DATABASE {database_name} TO {runtime_role}")
    finally:
        await conn.close()


async def _truncate_existing_data(admin_url: str) -> None:
    """Clear test data before migration resets.

    The regression suite may run after manual end-to-end validation has populated
    the shared local PostgreSQL test database. Downgrading across historical
    financial migrations with newer ledger rows can violate old constraints, so
    clear root tables first and let CASCADE remove tenant data.
    """

    engine = create_async_engine(admin_url)
    async with engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        existing_tables = (
            await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = ANY(:table_names)
                    """
                ),
                {"table_names": list(ROOT_TABLES)},
            )
        ).scalars()
        quoted_tables = [f'"{table_name}"' for table_name in existing_tables]
        if quoted_tables:
            await connection.execute(text(f"TRUNCATE {', '.join(quoted_tables)} CASCADE"))
    await engine.dispose()


async def _grant_runtime_privileges(admin_url: str, runtime_url: str) -> None:
    runtime = make_url(runtime_url).username
    if not runtime or admin_url == runtime_url:
        return
    quoted_runtime = _quote_identifier(runtime)
    engine = create_async_engine(admin_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {quoted_runtime}"))
        await connection.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                f"TO {quoted_runtime}"
            )
        )
        await connection.execute(
            text(
                "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public "
                f"TO {quoted_runtime}"
            )
        )
    await engine.dispose()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        environment="testing",
        database_url=TEST_DATABASE_URL,
        database_admin_url=TEST_DATABASE_ADMIN_URL,
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        cors_origins=["http://localhost:8081"],
        cookie_secure=False,
        rate_limit_enabled=False,
    )


@pytest.fixture(scope="session", autouse=True)
def migrated_database(test_settings: Settings) -> Iterator[None]:
    os.environ["DATABASE_URL"] = test_settings.database_url
    os.environ["DATABASE_MIGRATION_URL"] = test_settings.database_admin_url or ""
    os.environ["DATABASE_ADMIN_URL"] = test_settings.database_admin_url or ""
    os.environ["JWT_SECRET"] = TEST_JWT_SECRET
    get_settings.cache_clear()
    if BOOTSTRAP_MANAGED_TEST_DATABASE:
        asyncio.run(
            _ensure_managed_test_database(
                TEST_DATABASE_BOOTSTRAP_URL,
                TEST_DATABASE_ADMIN_URL,
                TEST_DATABASE_URL,
            )
        )
    if test_settings.database_admin_url is not None:
        asyncio.run(_truncate_existing_data(test_settings.database_admin_url))
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    if test_settings.database_admin_url is not None:
        asyncio.run(_grant_runtime_privileges(test_settings.database_admin_url, TEST_DATABASE_URL))
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_database(test_settings: Settings) -> AsyncIterator[None]:
    admin_url = test_settings.database_admin_url
    assert admin_url is not None
    await _truncate_existing_data(admin_url)
    yield
    await _truncate_existing_data(admin_url)


@pytest_asyncio.fixture
async def app(test_settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(test_settings)
    yield application
    await application.state.database.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
