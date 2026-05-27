"""Public re-export of CLI exit codes.

Lives in ``engine.policy`` so the CLI (Phase 02) can import a tiny module
without pulling the entire ``engine.errors`` graph (which transitively
imports redaction). Numbers come from ``engine.errors.codes`` — the
single source of truth.
"""

from __future__ import annotations

from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.errors.codes import exit_code_for as exit_code_for_error_code

__all__ = [
    "EXIT_SUCCESS",
    "EXIT_QUALITY_GATE_FAILED",
    "EXIT_CONFIG_ERROR",
    "EXIT_RUNTIME_ERROR",
    "EXIT_UNSAFE_TARGET",
    "EXIT_DEPENDENCY_MISSING",
    "EXIT_TEST_EXECUTION_FAILED",
    "EXIT_INTERNAL_ERROR",
    "exit_code_for_error_code",
]
