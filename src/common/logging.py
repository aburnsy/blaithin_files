"""Structured logging configuration.

When a scraper runs with a known source, all logs go to a single
``logs/<source>.log`` file, freshly overwritten each run. When no source
is set (e.g. tests, matching pipeline), file logging stays at the
``LOG_FILE`` path (if pre-set) or stdout only.
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from pathlib import Path

import structlog

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE: Path | None = None
_CONFIGURED = False


def configure(*, source: str | None = None, force: bool = False) -> None:
    """Initialise structlog + stdlib logging.

    If ``source`` is given, writes JSON lines to ``logs/<source>.log`` in
    overwrite mode. If ``LOG_FILE`` is pre-set (tests), writes to that path
    in append mode. Otherwise, stdout only.

    Idempotent unless ``force=True``.
    """
    global LOG_FILE, _CONFIGURED

    if _CONFIGURED and not force:
        return

    handlers: list[stdlib_logging.Handler] = []

    if source:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE = LOG_DIR / f"{source}.log"
        file_mode = "w"
    elif LOG_FILE is not None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_mode = "a"
    else:
        file_mode = None

    if file_mode is not None and LOG_FILE is not None:
        file_handler = stdlib_logging.FileHandler(LOG_FILE, encoding="utf-8", mode=file_mode)
        file_handler.setLevel(stdlib_logging.INFO)
        file_handler.setFormatter(stdlib_logging.Formatter("%(message)s"))
        handlers.append(file_handler)

    stream_handler = stdlib_logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdlib_logging.INFO)
    handlers.append(stream_handler)

    root = stdlib_logging.getLogger()
    root.handlers = handlers
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
    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a bound logger; auto-configures on first call."""
    if not _CONFIGURED:
        configure()
    return structlog.get_logger(name)
