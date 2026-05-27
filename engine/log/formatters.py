"""Log formatters for human and JSON modes."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import ClassVar

from engine.log.context import current_context

_BUILTIN_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


class JSONFormatter(logging.Formatter):
    """One JSON object per record. Fields: ts, level, logger, msg, extra, context."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, UTC).isoformat()
        extras: dict[str, object] = {
            k: v for k, v in record.__dict__.items() if k not in _BUILTIN_RECORD_ATTRS
        }
        payload: dict[str, object] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        ctx = current_context()
        if ctx:
            payload["context"] = ctx
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc_message"] = (
                str(record.exc_info[1]) if record.exc_info[1] is not None else None
            )
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class HumanFormatter(logging.Formatter):
    """Pretty-printed terminal output."""

    _LEVEL_COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[37m",  # white
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    _RESET: ClassVar[str] = "\033[0m"

    def __init__(self, *, color: bool = False) -> None:
        super().__init__()
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, UTC).strftime("%H:%M:%S")
        level = record.levelname
        if self.color:
            color = self._LEVEL_COLORS.get(level, "")
            level = f"{color}{level}{self._RESET}"
        ctx = current_context()
        prefix = f"[{ts}] {level} {record.name}:"
        if ctx:
            ctx_str = " ".join(f"{k}={v}" for k, v in sorted(ctx.items()))
            prefix = f"{prefix} ({ctx_str})"
        extras = {k: v for k, v in record.__dict__.items() if k not in _BUILTIN_RECORD_ATTRS}
        suffix = ""
        if extras:
            suffix = " " + " ".join(f"{k}={v!r}" for k, v in sorted(extras.items()))
        return f"{prefix} {record.getMessage()}{suffix}"


__all__ = ["JSONFormatter", "HumanFormatter"]
