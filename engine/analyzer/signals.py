"""Build :class:`FailureSignal` objects from runner outcomes (task 09.01).

The runner aggregator (Phase 08) produces a :class:`RunnerOutcome` with
per-test :class:`TestExecution` records. Phase 09 layers on top: for
each *failed* test it enriches the execution record with the
step / network / console events captured during the run, plus optional
test-case metadata (route, module) from the planner.

This module deliberately does NOT call the TS bridge — callers pass
already-parsed events. That keeps the analyzer pure and testable
without needing a live runner.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from engine.analyzer.models import (
    AttemptOutcome,
    ConsoleRecord,
    FailureSignal,
    NetworkRecord,
    StepRecord,
)
from engine.orchestrator.ts_bridge import (
    ConsoleEvent,
    NetworkResponseEvent,
    StepEndEvent,
    StepStartEvent,
)
from engine.runner.results import RunnerOutcome, TestExecution

# A typed alias for the events the analyzer cares about. Other event
# kinds (run.start, evidence, etc.) are aggregated by the runner; the
# analyzer does not need them.
_AnalyzerEvent = StepStartEvent | StepEndEvent | NetworkResponseEvent | ConsoleEvent


# Failed-status set: anything the analyzer reasons about. ``flaky`` is
# included because the analyzer's flake rule wants to confirm the test
# actually passed on a retry.
_FAILED_STATUSES = frozenset({"failed", "timed_out", "flaky"})


def build_failure_signal(
    execution: TestExecution,
    *,
    events: Iterable[_AnalyzerEvent] = (),
    module: str,
    route: str | None = None,
    fixture_failed: bool = False,
    error_name: str | None = None,
    error_stack: str | None = None,
    attempts: Sequence[AttemptOutcome] = (),
) -> FailureSignal:
    """Construct one :class:`FailureSignal` for ``execution``.

    The caller threads in:

    * ``events`` — the parsed TS events scoped to this test (filtered
      by ``test_id`` already; we do not re-filter to keep the analyzer
      a pure consumer).
    * ``module`` — which SentinelQA module ran this test (functional,
      a11y, security, ...). Defaults to the lifecycle's module name.
    * ``route`` — optional planner route the test exercised.
    * ``fixture_failed`` — True when the failure originated in a
      setup hook (auth / data seed).
    * ``error_name`` / ``error_stack`` — optional richer error data
      that ``TestExecution`` does not currently carry.
    * ``attempts`` — per-retry attempt records. When empty, we
      synthesize a single-attempt history from ``execution``.
    """

    steps: list[StepRecord] = []
    pending_starts: dict[str, str] = {}
    network: list[NetworkRecord] = []
    console: list[ConsoleRecord] = []

    for event in events:
        if isinstance(event, StepStartEvent):
            pending_starts[event.step_id] = event.name
        elif isinstance(event, StepEndEvent):
            name = pending_starts.pop(event.step_id, "<step>")
            steps.append(
                StepRecord(
                    step_id=event.step_id,
                    name=name,
                    duration_ms=event.duration_ms,
                    ok=event.ok,
                    error_message=event.error.message if event.error else None,
                )
            )
        elif isinstance(event, NetworkResponseEvent):
            network.append(
                NetworkRecord(
                    url=event.url,
                    method="GET",  # response event doesn't carry method; default
                    status_code=event.status,
                    duration_ms=event.duration_ms,
                )
            )
        elif isinstance(event, ConsoleEvent):
            console.append(
                ConsoleRecord(
                    level=event.level,
                    message=event.message,
                    source=event.source,
                )
            )

    if not attempts:
        attempts = (
            AttemptOutcome(
                attempt=0,
                status=_attempt_status(execution.status),  # type: ignore[arg-type]
                duration_ms=execution.duration_ms,
                error_message=execution.error_message,
            ),
        )

    status = execution.status if execution.status in _FAILED_STATUSES else "failed"
    return FailureSignal(
        test_id=execution.test_id,
        title=execution.title,
        file=execution.file,
        status=status,  # type: ignore[arg-type]
        duration_ms=execution.duration_ms,
        retries=execution.retries,
        attempts=tuple(attempts),
        error_message=execution.error_message,
        error_name=error_name,
        error_stack=error_stack,
        steps=tuple(steps),
        network=tuple(network),
        console=tuple(console),
        evidence=execution.evidence,
        module=module,
        route=route,
        fixture_failed=fixture_failed,
    )


def _attempt_status(
    status: str,
) -> str:
    """Map :class:`TestStatus` → :class:`AttemptOutcome.status`."""

    if status in {"passed", "failed", "timed_out", "skipped"}:
        return status
    if status == "flaky":
        # Last attempt of a flaky test passed; earlier failed. Default
        # to passed for the synthesized single attempt.
        return "passed"
    return "failed"


def build_module_error_signal(
    *,
    module: str,
    exc_type: str,
    exc_message: str,
) -> FailureSignal:
    """Build a synthetic signal for a module that errored before any
    test ran (CLAUDE §10 catch-all).

    The synthesized record has no steps/network/console (no test ran)
    so the analyzer falls back to :func:`categorize_module_error`. We
    still emit a :class:`FailureSignal` so the rest of the pipeline
    (hypothesis, repro, retry) can run uniformly.
    """

    return FailureSignal(
        test_id=f"module:{module}",
        title=f"{module} module failed to run",
        file=f"<module:{module}>",
        status="errored",
        duration_ms=0,
        retries=0,
        attempts=(
            AttemptOutcome(
                attempt=0,
                status="failed",
                duration_ms=0,
                error_message=exc_message[:2_048] if exc_message else None,
            ),
        ),
        error_message=exc_message[:2_048] if exc_message else None,
        error_name=exc_type[:128] if exc_type else None,
        module=module,
    )


def filter_failed(outcome: RunnerOutcome) -> tuple[TestExecution, ...]:
    """Return the executions the analyzer should reason about."""

    return tuple(t for t in outcome.tests if t.status in _FAILED_STATUSES)


__all__ = [
    "build_failure_signal",
    "build_module_error_signal",
    "filter_failed",
]
