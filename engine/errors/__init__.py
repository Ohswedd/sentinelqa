"""SentinelQA typed exception hierarchy (our engineering guidelines, the documentation).

Every exception that crosses a CLI/SDK boundary is a subclass of
:class:`SentinelError`. Each subclass maps to exactly one CLI exit code via
the registry in :mod:`engine.errors.codes`, so the CLI never needs to guess.

Wire format for SDK/MCP consumers: ``error.to_agent_message()`` returns a
dict suitable for serialization (redaction applied), keyed by:

- ``type`` — always ``"error"``
- ``code`` — short stable identifier (e.g. ``"E-CFG-001"``)
- ``message`` — human-readable summary, secrets redacted
- ``suggested_fix`` — actionable hint, also redacted
- ``context`` — structured technical metadata, redacted recursively
"""

from __future__ import annotations

from engine.errors.base import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigSchemaError,
    ConfigSecretInlineError,
    DependencyMissingError,
    DestructiveWithoutProofError,
    ForbiddenFlagError,
    InternalError,
    PluginError,
    QualityGateFailedError,
    SentinelError,
    TestExecutionError,
    UnknownHostError,
    UnsafeTargetError,
)
from engine.errors.codes import (
    ERROR_REGISTRY,
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
    ErrorCodeSpec,
    exit_code_for,
)

__all__ = [
    # Base + concrete exceptions
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
    "InternalError",
    "PluginError",
    # Exit-code constants + registry
    "EXIT_SUCCESS",
    "EXIT_QUALITY_GATE_FAILED",
    "EXIT_CONFIG_ERROR",
    "EXIT_RUNTIME_ERROR",
    "EXIT_UNSAFE_TARGET",
    "EXIT_DEPENDENCY_MISSING",
    "EXIT_TEST_EXECUTION_FAILED",
    "EXIT_INTERNAL_ERROR",
    "ERROR_REGISTRY",
    "ErrorCodeSpec",
    "exit_code_for",
]
