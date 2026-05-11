"""Structured logging configuration.

JSON to `logs/<date>.jsonl` (machine-readable) + pretty to stdout (human).
Call `configure()` once at the start of any entry point that should log.
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from datetime import date
from pathlib import Path

import structlog

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE: Path | None = None  # set by configure() based on date


def configure(*, force: bool = False) -> None:
    """Initialise structlog + stdlib logging. Idempotent unless force=True."""
    global LOG_FILE

    if LOG_FILE is not None and not force:
        return

    # Only set the default date-based path when LOG_FILE is None.
    # If the caller pre-set LOG_FILE (e.g. in tests via monkeypatch) keep it.
    if LOG_FILE is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE = LOG_DIR / f"{date.today().isoformat()}.jsonl"
    else:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_handler = stdlib_logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(stdlib_logging.INFO)
    file_handler.setFormatter(stdlib_logging.Formatter("%(message)s"))

    stream_handler = stdlib_logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdlib_logging.INFO)

    root = stdlib_logging.getLogger()
    root.handlers = [file_handler, stream_handler]
    root.setLevel(stdlib_logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(stdlib_logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a bound logger; auto-configures on first call."""
    if LOG_FILE is None:
        configure()
    return structlog.get_logger(name)
