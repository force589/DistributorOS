from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.api.router import api_router
from distributoros.core.config import Settings, get_settings
from distributoros.core.database import Database, get_session
from distributoros.core.errors import install_exception_handlers
from distributoros.core.logging import configure_logging
from distributoros.core.middleware import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.environment)
    database = Database(active_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await database.dispose()

    app = FastAPI(
        title="DistributorOS API",
        version="0.8.0",
        description=(
            "DistributorOS distribution management API."
        ),
        lifespan=lifespan,
    )
    app.state.database = database
    app.dependency_overrides[get_settings] = lambda: active_settings
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Client-Platform",
            "X-Request-ID",
        ],
    )
    install_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health/live", tags=["Health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"])
    async def ready(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str]:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}

    return app
