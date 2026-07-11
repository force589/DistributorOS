import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import Settings, get_settings
from distributoros.main import create_app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://distributoros_app:test-app-password@localhost:5432/distributoros_test",
)
TEST_DATABASE_ADMIN_URL = os.getenv(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+asyncpg://distributoros_admin:test-admin-password@localhost:5432/distributoros_test",
)
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
os.environ.setdefault("DATABASE_ADMIN_URL", TEST_DATABASE_ADMIN_URL)
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)


async def _truncate_existing_data(admin_url: str) -> None:
    """Clear test data before migration resets.

    The regression suite may run after manual end-to-end validation has populated
    the shared local PostgreSQL test database. Downgrading across historical
    financial migrations with newer ledger rows can violate old constraints, so
    clear root tables first and let CASCADE remove tenant data.
    """

    engine = create_async_engine(admin_url)
    async with engine.begin() as connection:
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
    os.environ["DATABASE_ADMIN_URL"] = test_settings.database_admin_url or ""
    os.environ["JWT_SECRET"] = TEST_JWT_SECRET
    get_settings.cache_clear()
    if test_settings.database_admin_url is not None:
        asyncio.run(_truncate_existing_data(test_settings.database_admin_url))
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
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
