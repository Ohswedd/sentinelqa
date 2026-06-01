"""Exception hierarchy ⟷ exit-code map tests (our product spec2, our engineering rules)."""

from __future__ import annotations

import pytest
from engine.errors import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
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
    UnknownHostError,
    UnsafeTargetError,
)

# Alias to avoid pytest treating the class as a test collection target.
from engine.errors import TestExecutionError as TestExecErr


@pytest.mark.parametrize(
    "exc_cls,expected_exit",
    [
        (ConfigFileNotFoundError, EXIT_CONFIG_ERROR),
        (ConfigSchemaError, EXIT_CONFIG_ERROR),
        (ConfigSecretInlineError, EXIT_CONFIG_ERROR),
        (UnsafeTargetError, EXIT_UNSAFE_TARGET),
        (UnknownHostError, EXIT_UNSAFE_TARGET),
        (DestructiveWithoutProofError, EXIT_UNSAFE_TARGET),
        (ForbiddenFlagError, EXIT_UNSAFE_TARGET),
        (DependencyMissingError, EXIT_DEPENDENCY_MISSING),
        (TestExecErr, EXIT_TEST_EXECUTION_FAILED),
        (QualityGateFailedError, EXIT_QUALITY_GATE_FAILED),
        (InternalError, EXIT_INTERNAL_ERROR),
    ],
)
def test_exit_code_mapping(exc_cls: type[SentinelError], expected_exit: int) -> None:
    instance = exc_cls("boom", technical_context={"k": "v"})
    assert instance.exit_code == expected_exit


def test_plugin_error_default_is_dependency_missing() -> None:
    e = PluginError(plugin="my-plugin", detail="ImportError")
    assert e.exit_code == EXIT_DEPENDENCY_MISSING


def test_template_substitution() -> None:
    err = UnknownHostError(host="google.com")
    assert "google.com" in err.message
    assert err.technical_context["host"] == "google.com"


def test_explicit_message_wins() -> None:
    err = ConfigSchemaError(message="custom override")
    assert err.message == "custom override"


def test_subclassing_preserves_code() -> None:
    assert ConfigFileNotFoundError("x", path="/tmp/missing").code == "E-CFG-001"


def test_unregistered_code_falls_back() -> None:
    err = SentinelError("nope", code="E-UNREGISTERED-999")
    # Falls back to the runtime-error exit code.
    assert err.exit_code == 3
