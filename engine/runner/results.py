"""Aggregate JSONL events into a typed :class:`RunnerOutcome`.

The TS runner emits one JSON event per stdout line. The
aggregator consumes that stream, builds per-test execution records
(status / duration / retries / evidence), aggregates module-level
metrics (P50 / P95 duration, flake-rate), captures environment context
for reproducibility, and persists ``module-results/<module-name>.json``
under the run artifact tree.

Aggregator behavior:

- Partial streams (process killed mid-run) produce an ``incomplete``
 status with whatever tests we already observed. No crash.
- Pass-on-retry is recorded as ``flaky``: the test surfaced a failure
 on attempt N and passed on attempt N+1. The Phase-14 score module
 reads ``RunnerOutcome.flake_rate`` to apply the configured
 ``policy.max_flake_rate`` gate.
- Evidence paths are stored as POSIX strings relative to the run dir
 when possible; absolute paths are preserved otherwise.
- The module-results artifact is written through
 :class:`engine.orchestrator.artifacts.ArtifactDirectory` so writes are
 atomic and redacted.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.ts_bridge import (
    EvidenceEvent,
    ProtocolParseError,
    RunEndEvent,
    RunStartEvent,
    TestEndEvent,
    TestStartEvent,
    parse_event,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODULE_RESULTS_SCHEMA_VERSION = "1"
"""Wire format of the ``module-results/<name>.json`` envelope."""

TestStatus = Literal["passed", "failed", "flaky", "skipped", "timed_out"]


# ---------------------------------------------------------------------------
# Wire types
# ---------------------------------------------------------------------------


class EnvironmentContext(BaseModel):
    """Reproducibility metadata captured per outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    browser: str = Field(min_length=1, max_length=32)
    browser_version: str = Field(min_length=1, max_length=64)
    os: str = Field(min_length=1, max_length=32)
    node_version: str | None = Field(default=None, max_length=64)
    playwright_version: str | None = Field(default=None, max_length=64)


class TestExecution(BaseModel):
    """One Playwright test's execution outcome.

    ``test_id`` is the TS-side identifier (Playwright assigns it based on
    test title + project + file). It is opaque to Python.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=512)
    file: str = Field(min_length=1, max_length=512)
    status: TestStatus
    duration_ms: int = Field(ge=0)
    retries: int = Field(ge=0, le=10)
    evidence: tuple[str, ...] = Field(default_factory=tuple)
    error_message: str | None = Field(default=None, max_length=2_048)


class RunnerOutcome(BaseModel):
    """Result of running one module's worth of tests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = MODULE_RESULTS_SCHEMA_VERSION
    module_result: ModuleResult
    tests: tuple[TestExecution, ...] = Field(default_factory=tuple)
    environment: EnvironmentContext | None = None
    flake_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    flaky_test_ids: tuple[str, ...] = Field(default_factory=tuple)
    quarantined_test_ids: tuple[str, ...] = Field(default_factory=tuple)
    incomplete: bool = False

    @classmethod
    def build(
        cls,
        *,
        module_name: str,
        module_id: str,
        status: ModuleStatus,
        tests: Sequence[TestExecution],
        findings: Sequence[Finding] = (),
        errors: Sequence[str] = (),
        duration_ms: int,
        environment: EnvironmentContext | None,
        metrics_extra: dict[str, float] | None = None,
        flaky_test_ids: Sequence[str] = (),
        quarantined_test_ids: Sequence[str] = (),
        incomplete: bool = False,
    ) -> RunnerOutcome:
        """Construct a :class:`RunnerOutcome` with derived metrics filled in."""

        durations = [t.duration_ms for t in tests if t.status not in {"skipped"}]
        metrics: dict[str, float | int] = {
            "tests_total": len(tests),
            "tests_passed": sum(1 for t in tests if t.status == "passed"),
            "tests_failed": sum(1 for t in tests if t.status == "failed"),
            "tests_flaky": sum(1 for t in tests if t.status == "flaky"),
            "tests_skipped": sum(1 for t in tests if t.status == "skipped"),
            "tests_timed_out": sum(1 for t in tests if t.status == "timed_out"),
        }
        if durations:
            metrics["duration_p50_ms"] = float(median(durations))
            metrics["duration_p95_ms"] = float(_p95(durations))
        if metrics_extra:
            metrics.update(metrics_extra)
        total_for_flake = max(len(tests) - metrics["tests_skipped"], 1)
        flake_rate = metrics["tests_flaky"] / total_for_flake

        module_result = ModuleResult(
            id=module_id,
            name=module_name,
            status=status,
            findings=tuple(findings),
            metrics=metrics,
            duration_ms=duration_ms,
            errors=tuple(errors),
        )
        return cls(
            module_result=module_result,
            tests=tuple(tests),
            environment=environment,
            flake_rate=flake_rate,
            flaky_test_ids=tuple(flaky_test_ids),
            quarantined_test_ids=tuple(quarantined_test_ids),
            incomplete=incomplete,
        )


def _p95(values: Sequence[int]) -> float:
    """Return the 95th-percentile of ``values`` using the nearest-rank method."""

    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    # Nearest-rank: ceil(0.95 * N) - 1 (0-indexed).
    rank = max(int(round(0.95 * len(ordered))) - 1, 0)
    return float(ordered[rank])


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


class _TestAccumulator:
    """Per-test mutable record built up while streaming events."""

    __slots__ = (
        "test_id",
        "title",
        "file",
        "started_ms",
        "duration_ms",
        "status",
        "retries",
        "evidence",
        "error_message",
        "attempts",
    )

    def __init__(self, test_id: str, title: str, file: str) -> None:
        self.test_id = test_id
        self.title = title
        self.file = file
        self.started_ms: int | None = None
        self.duration_ms = 0
        self.status: TestStatus = "skipped"
        self.retries = 0
        self.evidence: list[str] = []
        self.error_message: str | None = None
        self.attempts: list[tuple[TestStatus, int]] = []

    def finalize(self) -> TestExecution:
        # Pass-on-retry => flaky.
        if (
            self.attempts
            and self.attempts[-1][0] == "passed"
            and any(att[0] in {"failed", "timed_out"} for att in self.attempts[:-1])
        ):
            self.status = "flaky"
        # Sum all attempts' durations so callers see the cumulative cost.
        self.duration_ms = sum(d for _, d in self.attempts) or self.duration_ms
        return TestExecution(
            test_id=self.test_id,
            title=self.title or "<unnamed>",
            file=self.file or "<unknown>",
            status=self.status,
            duration_ms=self.duration_ms,
            retries=self.retries,
            evidence=tuple(self.evidence),
            error_message=self.error_message,
        )


async def aggregate(
    events: AsyncIterator[Any],
    *,
    module_name: str,
    module_id: str,
    environment: EnvironmentContext | None = None,
    quarantined_test_ids: Sequence[str] = (),
) -> RunnerOutcome:
    """Consume a TS event stream and produce a :class:`RunnerOutcome`."""

    accumulators: dict[str, _TestAccumulator] = {}
    errors: list[str] = []
    incomplete = True  # Flips to False only when a run.end event arrives.
    started_at: datetime | None = None
    finished_at: datetime | None = None
    run_status: str | None = None

    async for event in events:
        if isinstance(event, RunStartEvent):
            started_at = event.started_at
            continue
        if isinstance(event, RunEndEvent):
            finished_at = event.finished_at
            run_status = event.status
            incomplete = False
            continue
        if isinstance(event, TestStartEvent):
            accumulators.setdefault(
                event.test_id,
                _TestAccumulator(event.test_id, event.title, event.file),
            )
            continue
        if isinstance(event, TestEndEvent):
            acc = accumulators.setdefault(
                event.test_id,
                _TestAccumulator(event.test_id, "<unknown>", "<unknown>"),
            )
            acc.status = event.status
            acc.duration_ms = event.duration_ms
            acc.retries = event.retries
            acc.attempts.append((event.status, event.duration_ms))
            if event.error is not None:
                acc.error_message = event.error.message
            continue
        if isinstance(event, EvidenceEvent):
            if event.test_id is None:
                continue
            acc = accumulators.setdefault(
                event.test_id,
                _TestAccumulator(event.test_id, "<unknown>", "<unknown>"),
            )
            acc.evidence.append(event.path)
            continue
        # We don't crash on other event kinds (step.*, network.*, etc.);
        # the aggregator's contract is per-test, not per-step.

    executions = sorted(
        (acc.finalize() for acc in accumulators.values()),
        key=lambda t: t.test_id,
    )
    flaky_ids = tuple(t.test_id for t in executions if t.status == "flaky")

    duration_ms = _compute_total_duration(
        executions=executions,
        started_at=started_at,
        finished_at=finished_at,
    )
    status = _derive_module_status(
        executions=executions,
        run_status=run_status,
        incomplete=incomplete,
        quarantined=set(quarantined_test_ids),
    )
    if incomplete:
        errors.append("test run did not emit run.end (process was interrupted)")
    return RunnerOutcome.build(
        module_name=module_name,
        module_id=module_id,
        status=status,
        tests=executions,
        errors=errors,
        duration_ms=duration_ms,
        environment=environment,
        flaky_test_ids=flaky_ids,
        quarantined_test_ids=tuple(quarantined_test_ids),
        incomplete=incomplete,
    )


def _compute_total_duration(
    *,
    executions: Sequence[TestExecution],
    started_at: datetime | None,
    finished_at: datetime | None,
) -> int:
    if started_at is not None and finished_at is not None:
        delta = finished_at - started_at
        ms = int(delta.total_seconds() * 1000)
        if ms > 0:
            return ms
    return sum(t.duration_ms for t in executions)


def _derive_module_status(
    *,
    executions: Sequence[TestExecution],
    run_status: str | None,
    incomplete: bool,
    quarantined: set[str],
) -> ModuleStatus:
    if incomplete:
        return "incomplete"
    if run_status == "interrupted":
        return "incomplete"
    if run_status == "errored":
        return "errored"
    blocking_fail = any(
        t.status in {"failed", "timed_out"} and t.test_id not in quarantined for t in executions
    )
    if blocking_fail:
        return "failed"
    if executions and all(t.status == "skipped" for t in executions):
        return "skipped"
    return "passed"


# ---------------------------------------------------------------------------
# Convenience: sync parser for non-async callers (tests, fixtures)
# ---------------------------------------------------------------------------


async def aggregate_lines(
    lines: Sequence[str],
    *,
    module_name: str,
    module_id: str,
    environment: EnvironmentContext | None = None,
    quarantined_test_ids: Sequence[str] = (),
) -> RunnerOutcome:
    """Aggregate a sequence of JSONL strings (one event per element).

    Lines that fail to parse are recorded as errors but do NOT abort the
    aggregation — partial streams are first-class.
    """

    async def _iter() -> AsyncIterator[Any]:
        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield parse_event(stripped)
            except ProtocolParseError:
                # Skip unparseable line; let the run-end gate decide
                # whether the run is incomplete.
                continue

    return await aggregate(
        _iter(),
        module_name=module_name,
        module_id=module_id,
        environment=environment,
        quarantined_test_ids=quarantined_test_ids,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def write_module_results(
    artifacts: ArtifactDirectory,
    outcome: RunnerOutcome,
) -> Path:
    """Persist ``module-results/<module-name>.json`` for ``outcome``."""

    module_name = outcome.module_result.name
    payload: dict[str, Any] = {
        "schema_version": outcome.schema_version,
        "written_at": datetime.now(UTC).isoformat(),
        "module": module_name,
        "module_result": outcome.module_result.to_dict(),
        "environment": outcome.environment.model_dump(mode="json")
        if outcome.environment is not None
        else None,
        "flake_rate": outcome.flake_rate,
        "flaky_test_ids": list(outcome.flaky_test_ids),
        "quarantined_test_ids": list(outcome.quarantined_test_ids),
        "incomplete": outcome.incomplete,
        "tests": [t.model_dump(mode="json") for t in outcome.tests],
    }
    # Use write_text so we can place it under a sub-directory.
    out_dir = artifacts.subdir("module-results")
    target = out_dir / f"{module_name}.json"
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target


__all__ = [
    "EnvironmentContext",
    "MODULE_RESULTS_SCHEMA_VERSION",
    "RunnerOutcome",
    "TestExecution",
    "TestStatus",
    "aggregate",
    "aggregate_lines",
    "write_module_results",
]
