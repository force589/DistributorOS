import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from distributoros.core.config import get_settings
from distributoros.core.logging import configure_logging
from distributoros.modules.inventory.reconciliation import (
    InventoryReconciliationService,
    RebuildBlockedError,
    ReconciliationInvariantError,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare inventory projections with immutable movement history across all tenants."
        )
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Explicitly delete and recreate every stock projection in one transaction.",
    )
    return parser


async def _run(*, rebuild: bool) -> int:
    settings = get_settings()
    configure_logging(settings.environment, stream=sys.stderr)
    if settings.database_admin_url is None:
        print(
            "DATABASE_ADMIN_URL is required for cross-tenant inventory reconciliation.",
            file=sys.stderr,
        )
        return 1

    engine = create_async_engine(settings.database_admin_url, pool_pre_ping=True)
    service = InventoryReconciliationService(engine)
    try:
        if rebuild:
            try:
                result = await service.rebuild()
            except (RebuildBlockedError, ReconciliationInvariantError) as exc:
                print(exc.report.model_dump_json(indent=2))
                print(str(exc), file=sys.stderr)
                return 3
            print(result.model_dump_json(indent=2))
            return 0

        report = await service.reconcile()
        print(report.model_dump_json(indent=2))
        return 0 if report.is_consistent else 2
    finally:
        await engine.dispose()


def main() -> None:
    arguments = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(rebuild=arguments.rebuild)))


if __name__ == "__main__":
    main()
