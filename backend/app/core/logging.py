from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import get_settings


def _force_utf8_streams() -> None:
    """Make stdout/stderr accept arbitrary unicode (emoji, Arabic) on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            pass


def configure_logging() -> None:
    _force_utf8_streams()
    settings = get_settings()

    level = getattr(logging, settings.log_level)

    logging.basicConfig(
        format="%(message)s",
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if settings.is_prod or settings.environment == "staging":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None, **bindings: Any) -> structlog.stdlib.BoundLogger:
    logger = structlog.get_logger(name) if name else structlog.get_logger()
    if bindings:
        logger = logger.bind(**bindings)
    return logger
