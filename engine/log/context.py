"""Context-variable backed log enrichment."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("sentinelqa_log_context", default={})


def current_context() -> dict[str, Any]:
    """Return a shallow copy of the active context."""

    return dict(_CONTEXT.get())


class LogContext:
    """Stack-based context for log enrichment.

    Use :func:`engine.log.log_context` for the contextmanager surface.
    """

    @staticmethod
    def push(fields: dict[str, Any]) -> Token[dict[str, Any]]:
        new = dict(_CONTEXT.get())
        new.update(fields)
        return _CONTEXT.set(new)

    @staticmethod
    def pop(token: Token[dict[str, Any]]) -> None:
        _CONTEXT.reset(token)

    @staticmethod
    def bind_run_id(run_id: str) -> None:
        """Permanently attach ``run_id`` to the current context."""

        new = dict(_CONTEXT.get())
        new["run_id"] = run_id
        _CONTEXT.set(new)


__all__ = ["LogContext", "current_context"]
