"""Smoke tests for engine.policy.exit_codes + engine.errors.codes.exit_code_for."""

from __future__ import annotations

from engine.errors.codes import exit_code_for
from engine.policy.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
    exit_code_for_error_code,
)


def test_constants_match_canonical_grid() -> None:
    assert (EXIT_SUCCESS, EXIT_QUALITY_GATE_FAILED, EXIT_CONFIG_ERROR) == (0, 1, 2)
    assert (EXIT_RUNTIME_ERROR, EXIT_UNSAFE_TARGET, EXIT_DEPENDENCY_MISSING) == (3, 4, 5)
    assert (EXIT_TEST_EXECUTION_FAILED, EXIT_INTERNAL_ERROR) == (6, 7)


def test_exit_code_for_registered() -> None:
    assert exit_code_for("E-CFG-001") == EXIT_CONFIG_ERROR
    assert exit_code_for("E-SAFE-001") == EXIT_UNSAFE_TARGET


def test_exit_code_for_unknown() -> None:
    assert exit_code_for("does-not-exist") == EXIT_RUNTIME_ERROR
    assert exit_code_for_error_code("does-not-exist") == EXIT_RUNTIME_ERROR
