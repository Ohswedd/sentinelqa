"""Shared fixtures for the analyzer unit tests."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from engine.analyzer.models import (
    AttemptOutcome,
    ConsoleRecord,
    FailureSignal,
    NetworkRecord,
    StepRecord,
)


def make_signal(
    *,
    test_id: str = "test:login",
    title: str = "user can sign in",
    file: str = "tests/sentinel/login.spec.ts",
    status: str = "failed",
    error_message: str | None = None,
    error_name: str | None = None,
    retries: int = 0,
    attempts: Sequence[AttemptOutcome] = (),
    steps: Sequence[StepRecord] = (),
    network: Sequence[NetworkRecord] = (),
    console: Sequence[ConsoleRecord] = (),
    evidence: Sequence[str] = (),
    module: str = "functional",
    route: str | None = None,
    fixture_failed: bool = False,
) -> FailureSignal:
    """Test factory — every field has a safe default."""

    return FailureSignal(
        test_id=test_id,
        title=title,
        file=file,
        status=status,  # type: ignore[arg-type]
        duration_ms=1234,
        retries=retries,
        attempts=tuple(attempts)
        or (
            AttemptOutcome(
                attempt=0,
                status="failed" if status != "flaky" else "passed",
                duration_ms=1234,
                error_message=error_message,
            ),
        ),
        error_message=error_message,
        error_name=error_name,
        steps=tuple(steps),
        network=tuple(network),
        console=tuple(console),
        evidence=tuple(evidence),
        module=module,
        route=route,
        fixture_failed=fixture_failed,
    )


@pytest.fixture
def make_signal_fixture() -> object:
    """Fixture wrapper so tests can use ``make_signal_fixture`` or call
    ``make_signal`` directly. The function above is the primary surface."""

    return make_signal
