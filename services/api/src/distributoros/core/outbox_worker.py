from __future__ import annotations

import argparse
import asyncio
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from distributoros.core.config import Settings, get_settings
from distributoros.core.logging import configure_logging
from distributoros.core.outbox import OutboxEvent


def _send_password_reset_email(settings: Settings, payload: dict[str, Any]) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP password-reset delivery is not configured.")
    recipient = str(payload["recipient"])
    reset_url = str(payload["reset_url"])
    message = EmailMessage()
    message["Subject"] = "Reset your DistributorOS password"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your DistributorOS account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {settings.password_reset_minutes} minutes. "
        "If you did not request this, you can ignore this email."
    )
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
        client.ehlo()
        if settings.smtp_starttls:
            client.starttls()
            client.ehlo()
        if settings.smtp_username and password:
            client.login(settings.smtp_username, password)
        client.send_message(message)


async def process_outbox_batch(
    session: AsyncSession,
    settings: Settings,
    *,
    batch_size: int = 20,
) -> int:
    statement = (
        select(OutboxEvent)
        .where(
            OutboxEvent.processed_at.is_(None),
            OutboxEvent.available_at <= datetime.now(UTC),
        )
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    events = list((await session.scalars(statement)).all())
    logger = structlog.get_logger("distributoros.outbox")
    for event in events:
        try:
            if event.event_type == "identity.password_reset_requested":
                await asyncio.to_thread(_send_password_reset_email, settings, event.payload)
            else:
                raise RuntimeError(f"Unsupported outbox event: {event.event_type}")
            event.processed_at = datetime.now(UTC)
            event.last_error = None
            logger.info(
                "outbox_event_processed",
                event_id=str(event.id),
                event_type=event.event_type,
            )
        except Exception as exc:  # noqa: BLE001 - worker must retain and retry failed deliveries.
            event.attempts += 1
            event.last_error = f"{type(exc).__name__}: {exc}"[:500]
            event.available_at = datetime.now(UTC) + timedelta(
                seconds=min(3600, 2 ** min(event.attempts, 10))
            )
            logger.error(
                "outbox_event_failed",
                event_id=str(event.id),
                event_type=event.event_type,
                attempts=event.attempts,
                exception_type=type(exc).__name__,
            )
    await session.flush()
    return len(events)


async def _run(*, once: bool, poll_seconds: float) -> None:
    settings = get_settings()
    configure_logging(settings.environment)
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        while True:
            async with sessions() as session, session.begin():
                processed = await process_outbox_batch(session, settings)
            if once:
                return
            if processed == 0:
                await asyncio.sleep(poll_seconds)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deliver DistributorOS transactional outbox events."
    )
    parser.add_argument("--once", action="store_true", help="Process one batch and exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    asyncio.run(_run(once=args.once, poll_seconds=max(0.25, args.poll_seconds)))


if __name__ == "__main__":
    main()
