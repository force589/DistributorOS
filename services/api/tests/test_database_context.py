from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from distributoros.core.config import Settings
from distributoros.core.database import Database, set_tenant_context


async def test_tenant_context_is_transaction_local_on_reused_pooled_connection(
    test_settings: Settings,
) -> None:
    database = Database(test_settings.database_url, pool_size=1, max_overflow=0)
    tenant_id = uuid4()
    try:
        async with database.session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            active_tenant = await session.scalar(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            assert active_tenant == str(tenant_id)

        async with database.session_factory() as session, session.begin():
            active_tenant = await session.scalar(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            assert active_tenant in (None, "")
    finally:
        await database.dispose()


async def test_preview_runtime_role_is_subject_to_migrated_rls_tables(
    test_settings: Settings,
) -> None:
    admin_url = test_settings.database_admin_url
    if admin_url is None:
        pytest.skip("No migration/admin URL configured for runtime-role ownership check.")
    if make_url(admin_url).username == make_url(test_settings.database_url).username:
        pytest.skip("Single-role local database cannot prove runtime ownership separation.")

    database = Database(test_settings.database_url, pool_size=1, max_overflow=0)
    try:
        await database.validate_runtime_role_supports_rls()
    finally:
        await database.dispose()
