"""Public error classes for SentinelQA (the documentation, our engineering rules).

Every error raised by the SDK at a public boundary is a subclass of
:class:`SentinelError`. Each has a stable ``code`` (e.g. ``E-CFG-001``),
a CLI-style ``exit_code`` for symmetry with the CLI, and a
``to_agent_message`` method that returns a redacted, schema-versioned
dict suitable for round-tripping to and from an LLM.

This module is the **only** public surface for errors. The SDK root
re-exports the most common ones for convenience::

 from sentinelqa import SentinelError, ConfigError, UnsafeTargetError

For reconstruction from an agent message::

 from sentinelqa.errors import from_dict
 err = from_dict(agent_message) # -> SentinelError subclass

The reconstructed instance carries the same ``code``, ``message``,
``suggested_fix``, ``exit_code``, and ``technical_context`` as the
original. Unknown codes fall back to a generic :class:`SentinelError`
instance whose ``code`` is preserved verbatim (our engineering rules — we
surface what we got, we do not invent a category).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engine.errors import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigSchemaError,
    ConfigSecretInlineError,
    DependencyMissingError,
    DestructiveWithoutProofError,
    ForbiddenFlagError,
    QualityGateFailedError,
    SentinelError,
    TestExecutionError,
    UnknownHostError,
    UnsafeTargetError,
)

# Stable ordering: a code's most specific subclass wins. The CLI maps
# codes by registry; the SDK reconstruction picks the same subclass so a
# round-tripped error compares equal in both `code` and `type`.
_CODE_TO_CLASS: dict[str, type[SentinelError]] = {
    "E-CFG-001": ConfigFileNotFoundError,
    "E-CFG-002": ConfigSchemaError,
    "E-CFG-003": ConfigSecretInlineError,
    "E-SAFE-001": UnknownHostError,
    "E-SAFE-002": DestructiveWithoutProofError,
    "E-SAFE-003": ForbiddenFlagError,
    "E-DEP-001": DependencyMissingError,
    "E-RUN-001": TestExecutionError,
    "E-QGATE-001": QualityGateFailedError,
}


def from_dict(agent_message: Mapping[str, Any]) -> SentinelError:
    """Reconstruct a :class:`SentinelError` from a redacted agent message.

    ``agent_message`` is the same shape :meth:`SentinelError.to_agent_message`
    produces — ``type``, ``code``, ``exit_code``, ``message``,
    ``suggested_fix``, ``context``.

    The reconstructed instance carries the original ``code``, ``message``,
    ``suggested_fix``, and ``exit_code``. Unknown codes degrade to a
    generic :class:`SentinelError` instance with the code preserved so
    downstream tooling can still log / route on it.
    """

    if not isinstance(agent_message, Mapping):
        raise TypeError(f"agent_message must be a mapping (got {type(agent_message).__name__!r})")
    code = agent_message.get("code")
    if not isinstance(code, str) or not code:
        raise ValueError("agent_message is missing a 'code' string")

    cls = _CODE_TO_CLASS.get(code, SentinelError)

    message = agent_message.get("message")
    if message is not None and not isinstance(message, str):
        raise ValueError("agent_message 'message' must be a string if present")

    suggested_fix = agent_message.get("suggested_fix")
    if suggested_fix is not None and not isinstance(suggested_fix, str):
        raise ValueError("agent_message 'suggested_fix' must be a string if present")

    exit_code = agent_message.get("exit_code")
    if exit_code is not None and not isinstance(exit_code, int):
        raise ValueError("agent_message 'exit_code' must be an int if present")

    context = agent_message.get("context") or {}
    if not isinstance(context, Mapping):
        raise ValueError("agent_message 'context' must be a mapping if present")

    return cls(
        message=message,
        code=code,
        exit_code=exit_code,
        suggested_fix=suggested_fix,
        technical_context=dict(context),
    )


__all__ = [
    "SentinelError",
    "ConfigError",
    "ConfigFileNotFoundError",
    "ConfigSchemaError",
    "ConfigSecretInlineError",
    "UnsafeTargetError",
    "UnknownHostError",
    "DestructiveWithoutProofError",
    "ForbiddenFlagError",
    "DependencyMissingError",
    "TestExecutionError",
    "QualityGateFailedError",
    "from_dict",
]
