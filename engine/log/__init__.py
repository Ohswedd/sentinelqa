"""Structured logging facility for SentinelQA (CLAUDE.md §13, §33).

One logger configuration for the whole process. CLI entry calls
:func:`configure_logging` once with the mode picked by the user
(``human``/``json``/``quiet``). Every log record passes through
:class:`engine.log.redaction_filter.RedactionFilter` before it touches
a stream, so accidentally logging a token cannot leak it.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Literal

from engine.log.context import LogContext, current_context
from engine.log.formatters import HumanFormatter, JSONFormatter
from engine.log.redaction_filter import RedactionFilter

LogMode = Literal["human", "json", "quiet"]

_SENTINEL_LOGGER = "sentinelqa"
_AUDIT_LOGGER = "sentinelqa.audit"


def configure_logging(
    *,
    mode: LogMode = "human",
    level: str = "INFO",
    run_id: str | None = None,
) -> None:
    """Configure the root SentinelQA logger.

    Called exactly once at CLI entry. Idempotent — repeated calls reset
    handlers in place, which lets test suites swap modes cleanly.
    """

    root = logging.getLogger(_SENTINEL_LOGGER)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Drop any prior handlers so the mode swap is clean.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.propagate = False

    redactor = RedactionFilter()

    if mode == "quiet":
        # Errors only — go to stderr so callers piping stdout still see clean JSON.
        err_handler = logging.StreamHandler(sys.stderr)
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(HumanFormatter(color=sys.stderr.isatty()))
        err_handler.addFilter(redactor)
        root.addHandler(err_handler)
        return

    if mode == "json":
        out_handler = logging.StreamHandler(sys.stdout)
        out_handler.setLevel(logging.INFO)
        out_handler.setFormatter(JSONFormatter())
        out_handler.addFilter(redactor)
        err_handler = logging.StreamHandler(sys.stderr)
        err_handler.setLevel(logging.WARNING)
        err_handler.setFormatter(JSONFormatter())
        err_handler.addFilter(redactor)
        # In JSON mode stdout only receives INFO; WARNING+ goes to stderr.
        out_handler.addFilter(lambda record: record.levelno < logging.WARNING)
        root.addHandler(out_handler)
        root.addHandler(err_handler)
        return

    # human mode: pretty-printed to stderr (so stdout stays clean for piped data).
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(HumanFormatter(color=sys.stderr.isatty()))
    handler.addFilter(redactor)
    root.addHandler(handler)

    if run_id is not None:
        LogContext.bind_run_id(run_id)


def get_logger(name: str) -> logging.Logger:
    """Return a child of the SentinelQA logger by dotted ``name``."""

    if not name.startswith(_SENTINEL_LOGGER):
        name = f"{_SENTINEL_LOGGER}.{name}"
    return logging.getLogger(name)


@contextmanager
def log_context(**fields: Any) -> Generator[None, None, None]:
    """Push ``fields`` onto the LogContext for the duration of the block."""

    token = LogContext.push(fields)
    try:
        yield
    finally:
        LogContext.pop(token)


__all__ = [
    "configure_logging",
    "get_logger",
    "log_context",
    "LogContext",
    "current_context",
    "LogMode",
]
