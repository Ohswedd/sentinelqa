"""Coverage for edge cases in :mod:`engine.runner.results`."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from engine.orchestrator.artifacts import ArtifactDirectory
from engine.runner.results import (
    RunnerOutcome,
    TestExecution,
    _p95,
    aggregate_lines,
    write_module_results,
)


def test_p95_empty_returns_zero() -> None:
    assert _p95([]) == 0.0


def test_p95_single_value() -> None:
    assert _p95([42]) == 42.0


def test_p95_distribution() -> None:
    # 20 values 1..20; nearest-rank 95th-percentile is the 19th (value 19).
    assert _p95(list(range(1, 21))) == 19.0


def test_aggregate_handles_evidence_without_test_id() -> None:
    lines = [
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "run.start",
                "run_id": "RUN-EVAAAAAAAAA",
                "target": "http://localhost",
                "started_at": "2026-05-28T12:00:00+00:00",
                "seq": 1,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
        # Evidence with NO test_id — must be silently dropped.
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "evidence",
                "evidence_kind": "screenshot",
                "path": "evidence/orphan.png",
                "label": "orphan",
                "seq": 2,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "run.end",
                "run_id": "RUN-EVAAAAAAAAA",
                "finished_at": "2026-05-28T12:00:01+00:00",
                "status": "passed",
                "tests_total": 0,
                "tests_failed": 0,
                "seq": 3,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
    ]
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-ORPHAAAAAAAA")
    )
    assert outcome.tests == ()
    assert outcome.module_result.status == "passed"


def test_write_module_results_without_environment(tmp_path: Path) -> None:
    outcome = RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-NOENVAAAAAAA",
        status="passed",
        tests=(),
        duration_ms=0,
        environment=None,
    )
    artifacts = ArtifactDirectory(tmp_path)
    target = write_module_results(artifacts, outcome)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["environment"] is None


def test_aggregate_errored_run_status_is_errored() -> None:
    lines = [
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "run.start",
                "run_id": "RUN-ERRAAAAAAAA",
                "target": "http://localhost",
                "started_at": "2026-05-28T12:00:00+00:00",
                "seq": 1,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "run.end",
                "run_id": "RUN-ERRAAAAAAAA",
                "finished_at": "2026-05-28T12:00:01+00:00",
                "status": "errored",
                "tests_total": 0,
                "tests_failed": 0,
                "seq": 2,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
    ]
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-ERRAAAAAAAAA")
    )
    assert outcome.module_result.status == "errored"


def test_aggregate_interrupted_run_status_is_incomplete() -> None:
    lines = [
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "run.start",
                "run_id": "RUN-INTAAAAAAAA",
                "target": "http://localhost",
                "started_at": "2026-05-28T12:00:00+00:00",
                "seq": 1,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
        json.dumps(
            {
                "schema_version": "1.0.0",
                "type": "run.end",
                "run_id": "RUN-INTAAAAAAAA",
                "finished_at": "2026-05-28T12:00:01+00:00",
                "status": "interrupted",
                "tests_total": 0,
                "tests_failed": 0,
                "seq": 2,
                "ts": "2026-05-28T12:00:00+00:00",
            }
        ),
    ]
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-INTAAAAAAAAA")
    )
    assert outcome.module_result.status == "incomplete"


def test_metrics_extra_merges_into_module_metrics() -> None:
    tests = (
        TestExecution(
            test_id="t1",
            title="t",
            file="t.spec.ts",
            status="passed",
            duration_ms=100,
            retries=0,
        ),
    )
    outcome = RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-MXAAAAAAAAAA",
        status="passed",
        tests=tests,
        duration_ms=100,
        environment=None,
        metrics_extra={"network_requests": 17.0},
    )
    assert outcome.module_result.metrics["network_requests"] == 17.0
