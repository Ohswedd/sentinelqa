"""Error model for the MCP server (ADR-0023).

JSON-RPC 2.0 reserves the ``-32700..-32600`` range for transport-level
errors. Application errors live at ``-32001`` and carry the SentinelQA
exit code + the original agent-message payload from
``SentinelError.to_agent_message()`` so the agent can route on
``code`` deterministically.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engine.errors.base import SentinelError

# JSON-RPC 2.0 standard codes.
JSONRPC_PARSE_ERROR: int = -32700
JSONRPC_INVALID_REQUEST: int = -32600
JSONRPC_METHOD_NOT_FOUND: int = -32601
JSONRPC_INVALID_PARAMS: int = -32602
JSONRPC_INTERNAL_ERROR: int = -32603

# SentinelQA application errors live in the implementation-defined
# range (-32099..-32000).
JSONRPC_APPLICATION_ERROR: int = -32001


class ToolError(Exception):
    """An error raised by a tool implementation.

    ``code`` is the SentinelQA error code (e.g. ``"UNSAFE_TARGET"``).
    ``exit_code`` follows the canonical 0..7 grid (the documentation). ``data``
    is a redacted dict shipped inside the JSON-RPC error's ``data``
    field — typically the output of ``SentinelError.to_agent_message()``.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int,
        suggested_fix: str | None = None,
        technical_context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.suggested_fix = suggested_fix
        self.technical_context: dict[str, Any] = dict(technical_context or {})

    def to_agent_message(self) -> dict[str, Any]:
        """Return the redacted agent-message payload for this error.

        Shape matches :meth:`engine.errors.SentinelError.to_agent_message`
        so MCP error payloads round-trip through the SDK's
        :func:`sentinelqa.errors.from_dict`.
        """

        from engine.policy.redaction import redact

        payload: dict[str, Any] = {
            "type": "error",
            "code": self.code,
            "exit_code": self.exit_code,
            "message": str(self),
            "suggested_fix": self.suggested_fix or "",
            "context": dict(self.technical_context),
        }
        redacted = redact(payload)
        assert isinstance(redacted, dict)
        return redacted

    @classmethod
    def from_sentinel_error(cls, exc: SentinelError) -> ToolError:
        """Lift a :class:`SentinelError` into a :class:`ToolError`."""

        return cls(
            code=exc.code,
            message=exc.message,
            exit_code=exc.exit_code,
            suggested_fix=exc.suggested_fix,
            technical_context=dict(getattr(exc, "technical_context", {}) or {}),
        )


__all__ = [
    "JSONRPC_APPLICATION_ERROR",
    "JSONRPC_INTERNAL_ERROR",
    "JSONRPC_INVALID_PARAMS",
    "JSONRPC_INVALID_REQUEST",
    "JSONRPC_METHOD_NOT_FOUND",
    "JSONRPC_PARSE_ERROR",
    "ToolError",
]
