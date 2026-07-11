from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text
from starlette.requests import Request

from distributoros.core.config import Settings
from distributoros.core.database import Database
from distributoros.core.errors import AppError


async def enforce_rate_limit(
    request: Request,
    settings: Settings,
    *,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    if not settings.rate_limit_enabled:
        return
    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=now.timestamp() % window_seconds)
    expires_at = window_start + timedelta(seconds=window_seconds)
    key_hash = hashlib.sha256(
        f"{scope}:{identity}:{settings.jwt_secret.get_secret_value()}".encode()
    ).hexdigest()
    database: Database = request.app.state.database
    async with database.session_factory() as limiter_session, limiter_session.begin():
        count = await limiter_session.scalar(
            text(
                """
                INSERT INTO request_rate_limits
                    (scope, key_hash, window_started_at, expires_at, request_count)
                VALUES (:scope, :key_hash, :window_started_at, :expires_at, 1)
                ON CONFLICT (scope, key_hash, window_started_at)
                DO UPDATE SET request_count = request_rate_limits.request_count + 1
                RETURNING request_count
                """
            ),
            {
                "scope": scope,
                "key_hash": key_hash,
                "window_started_at": window_start,
                "expires_at": expires_at,
            },
        )
    if int(count or 0) <= limit:
        return
    retry_after = max(1, int((expires_at - now).total_seconds()) + 1)
    structlog.get_logger("distributoros.security").warning(
        "rate_limit_exceeded",
        scope=scope,
        retry_after=retry_after,
    )
    raise AppError(
        status_code=429,
        code="RATE_LIMIT_EXCEEDED",
        message=f"Too many requests. Wait {retry_after} seconds and try again.",
        headers={"Retry-After": str(retry_after)},
    )
