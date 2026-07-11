import logging
import sys
from typing import TextIO

import structlog


def configure_logging(environment: str, *, stream: TextIO | None = None) -> None:
    output = stream or sys.stdout
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: structlog.types.Processor
    if environment == "development":
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    logging.basicConfig(format="%(message)s", stream=output, level=logging.INFO)
    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=True,
    )
