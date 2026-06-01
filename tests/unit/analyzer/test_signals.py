"""FailureSignal builder tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engine.analyzer.signals import (
    build_failure_signal,
    build_module_error_signal,
    filter_failed,
)
from engine.orchestrator.ts_bridge import (
    ConsoleEvent,
    NetworkResponseEvent,
    SerializedError,
    StepEndEvent,
    StepStartEvent,
)
from engine.runner.results import RunnerOutcome, TestExecution


def _make_test_execution(**kwargs: Any) -> TestExecution:
    base: dict[str, Any] = dict(
        test_id="test:1",
        title="example",
        file="tests/e.spec.ts",
        status="failed",
        duration_ms=100,
        retries=0,
        evidence=(),
        error_message="boom",
    )
    base.update(kwargs)
    return TestExecution(**base)


def _ts() -> datetime:
    return datetime.now(UTC)


def _envelope(seq: int = 1) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "seq": seq, "ts": _ts()}


def test_build_failure_signal_captures_steps():
    execution = _make_test_execution()
    events = [
        StepStartEvent(type="step.start", step_id="s1", name="click[Submit]", **_envelope(1)),
        StepEndEvent(
            type="step.end",
            step_id="s1",
            duration_ms=50,
            ok=False,
            error=SerializedError(name="TimeoutError", message="timeout"),
            **_envelope(2),
        ),
    ]
    signal = build_failure_signal(execution, events=events, module="functional")
    assert len(signal.steps) == 1
    assert signal.steps[0].name == "click[Submit]"
    assert signal.steps[0].ok is False
    assert signal.steps[0].error_message == "timeout"


def test_build_failure_signal_captures_network():
    execution = _make_test_execution()
    events = [
        NetworkResponseEvent(
            type="network.response",
            request_id="r1",
            url="https://example.test/api",
            status=500,
            duration_ms=44,
            **_envelope(1),
        ),
    ]
    signal = build_failure_signal(execution, events=events, module="api")
    assert len(signal.network) == 1
    assert signal.network[0].status_code == 500


def test_build_failure_signal_captures_console():
    execution = _make_test_execution()
    events = [
        ConsoleEvent(
            type="console",
            level="error",
            message="boom",
            source="page",
            **_envelope(1),
        ),
    ]
    signal = build_failure_signal(execution, events=events, module="functional")
    assert len(signal.console) == 1
    assert signal.console[0].level == "error"


def test_build_failure_signal_synthesizes_attempts_when_none_provided():
    execution = _make_test_execution(status="failed", duration_ms=1234, error_message="boom")
    signal = build_failure_signal(execution, module="functional")
    assert len(signal.attempts) == 1
    assert signal.attempts[0].status == "failed"
    assert signal.attempts[0].duration_ms == 1234


def test_build_failure_signal_status_coerces_passed_to_failed():
    # Pass-only executions shouldn't reach the analyzer, but if a caller
    # does pass one we coerce to a failure status so the model validates.
    execution = _make_test_execution(status="passed")
    signal = build_failure_signal(execution, module="functional")
    assert signal.status == "failed"


def test_build_failure_signal_handles_step_without_start():
    """A step.end with no matching step.start uses a placeholder name."""

    execution = _make_test_execution()
    events = [
        StepEndEvent(
            type="step.end",
            step_id="orphan",
            duration_ms=10,
            ok=True,
            **_envelope(1),
        ),
    ]
    signal = build_failure_signal(execution, events=events, module="functional")
    assert signal.steps[0].name == "<step>"


def test_build_module_error_signal_uses_synthetic_test_id():
    signal = build_module_error_signal(
        module="api",
        exc_type="ConnectionError",
        exc_message="refused",
    )
    assert signal.test_id == "module:api"
    assert signal.module == "api"
    assert signal.status == "errored"
    assert signal.error_name == "ConnectionError"


def test_build_failure_signal_uses_provided_attempts():
    execution = _make_test_execution(status="failed")
    from engine.analyzer.models import AttemptOutcome

    attempts = (
        AttemptOutcome(attempt=0, status="failed", duration_ms=10, error_message="a"),
        AttemptOutcome(attempt=1, status="failed", duration_ms=12, error_message="b"),
    )
    signal = build_failure_signal(execution, module="functional", attempts=attempts)
    assert len(signal.attempts) == 2
    assert signal.attempts[1].error_message == "b"


def test_build_failure_signal_flaky_status_synthesizes_passed_attempt():
    execution = _make_test_execution(status="flaky")
    signal = build_failure_signal(execution, module="functional")
    assert signal.attempts[0].status == "passed"


def test_build_failure_signal_other_status_coerces_to_failed_attempt():
    # An "errored"-shaped TestExecution isn't valid (the enum tops at
    # passed/failed/timed_out/skipped/flaky for TestExecution), so we
    # rely on the coerce by handing in an unknown literal via the
    # module_error builder path.
    from engine.analyzer.signals import _attempt_status

    assert _attempt_status("passed") == "passed"
    assert _attempt_status("failed") == "failed"
    assert _attempt_status("flaky") == "passed"
    assert _attempt_status("anything_else") == "failed"


def test_filter_failed_drops_passed_and_skipped():
    outcome = RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-FUNCAAAAAAAA",
        status="failed",
        tests=[
            _make_test_execution(test_id="pass:1", status="passed"),
            _make_test_execution(test_id="fail:1", status="failed"),
            _make_test_execution(test_id="skip:1", status="skipped"),
            _make_test_execution(test_id="flaky:1", status="flaky"),
        ],
        duration_ms=100,
        environment=None,
    )
    failed = filter_failed(outcome)
    ids = {t.test_id for t in failed}
    assert ids == {"fail:1", "flaky:1"}
