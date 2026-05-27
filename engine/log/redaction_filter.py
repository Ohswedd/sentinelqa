"""Logging filter that scrubs secrets before they reach a stream."""

from __future__ import annotations

import logging

from engine.policy.redaction import redact


class RedactionFilter(logging.Filter):
    """Filter every record's ``msg`` and ``args``/``extra`` through :func:`redact`."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        # args may be a tuple OR a mapping (logging's `%`-style interpolation).
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(redact(a) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: redact(v) for k, v in record.args.items()}
        # Custom extras live on the record itself, prefixed with user keys.
        # Scrub everything that isn't a built-in logging attribute.
        for key, value in list(record.__dict__.items()):
            if key in _BUILTIN_RECORD_ATTRS:
                continue
            try:
                record.__dict__[key] = redact(value)
            except Exception:  # pragma: no cover — defensive
                # Logging must never crash because of redaction errors —
                # at worst we replace the value with an obvious marker.
                record.__dict__[key] = "[REDACTED:filter_error]"
        return True


# Set of attributes the `logging` module itself owns on a LogRecord. Anything
# outside this set is treated as user-provided ``extra=`` data and must be
# redacted.
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
    }
)


__all__: list[str] = ["RedactionFilter"]
