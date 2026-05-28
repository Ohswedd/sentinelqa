"""Unit tests for the JSONL → :class:`RunnerOutcome` aggregator (08.05)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import pytest
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.runner.results import (
    EnvironmentContext,
    aggregate_lines,
    write_module_results,
)


def _event(**fields: object) -> str:
    payload = {
        "schema_version": "1.0.0",
        "seq": fields.pop("seq", 1),
        "ts": fields.pop("ts", "2026-05-28T12:00:00+00:00"),
        **fields,
    }
    return json.dumps(payload)


def _run_full(seq_offset: int = 0) -> list[str]:
    return [
        _event(
            type="run.start",
            run_id="RUN-LOCAL",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
            seq=1 + seq_offset,
        ),
        _event(
            type="test.start",
            test_id="t1",
            title="login passes",
            file="login.spec.ts",
            seq=2 + seq_offset,
        ),
        _event(
            type="test.end",
            test_id="t1",
            duration_ms=500,
            status="passed",
            retries=0,
            seq=3 + seq_offset,
        ),
        _event(
            type="test.start",
            test_id="t2",
            title="signup fails",
            file="signup.spec.ts",
            seq=4 + seq_offset,
        ),
        _event(
            type="test.end",
            test_id="t2",
            duration_ms=2200,
            status="failed",
            retries=0,
            error={"name": "Error", "message": "expected element"},
            seq=5 + seq_offset,
        ),
        _event(
            type="run.end",
            run_id="RUN-LOCAL",
            finished_at="2026-05-28T12:00:30+00:00",
            status="failed",
            tests_total=2,
            tests_failed=1,
            seq=6 + seq_offset,
        ),
    ]


def _run_event_loop(coro: Any) -> Any:
    return asyncio.run(coro)


def test_aggregate_full_stream_passes_and_fails() -> None:
    lines = _run_full()

    outcome = _run_event_loop(
        aggregate_lines(lines, module_name="functional", module_id="MOD-FUNCAAAAAAAA")
    )

    assert outcome.module_result.status == "failed"
    assert outcome.module_result.metrics["tests_total"] == 2
    assert outcome.module_result.metrics["tests_passed"] == 1
    assert outcome.module_result.metrics["tests_failed"] == 1
    assert {t.test_id for t in outcome.tests} == {"t1", "t2"}
    assert outcome.incomplete is False
    assert outcome.flake_rate == 0.0
    assert outcome.module_result.duration_ms > 0
    assert "duration_p50_ms" in outcome.module_result.metrics


def test_aggregate_partial_stream_marks_incomplete() -> None:
    lines = _run_full()
    # Drop run.end to simulate an interrupted child.
    lines = lines[:-1]

    outcome = _run_event_loop(
        aggregate_lines(lines, module_name="functional", module_id="MOD-FUNCAAAAAAAA")
    )

    assert outcome.module_result.status == "incomplete"
    assert outcome.incomplete is True
    assert any("did not emit run.end" in err for err in outcome.module_result.errors)


def test_aggregate_pass_on_retry_is_flaky() -> None:
    lines = [
        _event(
            type="run.start",
            run_id="RUN-FLAKY",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
        ),
        _event(type="test.start", test_id="t1", title="flaky test", file="flaky.spec.ts", seq=2),
        _event(
            type="test.end",
            test_id="t1",
            duration_ms=300,
            status="failed",
            retries=0,
            error={"name": "Error", "message": "first try"},
            seq=3,
        ),
        _event(type="test.end", test_id="t1", duration_ms=400, status="passed", retries=1, seq=4),
        _event(
            type="run.end",
            run_id="RUN-FLAKY",
            finished_at="2026-05-28T12:00:01+00:00",
            status="passed",
            tests_total=1,
            tests_failed=0,
            seq=5,
        ),
    ]

    outcome = _run_event_loop(
        aggregate_lines(lines, module_name="functional", module_id="MOD-FLAKAAAAAAAA")
    )

    assert outcome.module_result.status == "passed"
    flaky_tests = [t for t in outcome.tests if t.status == "flaky"]
    assert len(flaky_tests) == 1
    assert flaky_tests[0].test_id == "t1"
    assert outcome.flaky_test_ids == ("t1",)
    assert outcome.flake_rate == pytest.approx(1.0)
    # Combined duration sums all attempts.
    assert flaky_tests[0].duration_ms == 700


def test_aggregate_quarantined_failure_does_not_flip_module_to_failed() -> None:
    lines = [
        _event(
            type="run.start",
            run_id="RUN-QUAR",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
        ),
        _event(type="test.start", test_id="t1", title="known broken", file="broken.spec.ts", seq=2),
        _event(type="test.end", test_id="t1", duration_ms=100, status="failed", retries=0, seq=3),
        _event(
            type="run.end",
            run_id="RUN-QUAR",
            finished_at="2026-05-28T12:00:01+00:00",
            status="failed",
            tests_total=1,
            tests_failed=1,
            seq=4,
        ),
    ]

    outcome = _run_event_loop(
        aggregate_lines(
            lines,
            module_name="functional",
            module_id="MOD-QUARAAAAAAAA",
            quarantined_test_ids=("t1",),
        )
    )

    # The blocking-failure check ignores quarantined tests, so the module
    # reports passed.
    assert outcome.module_result.status == "passed"
    assert outcome.quarantined_test_ids == ("t1",)


def test_aggregate_records_evidence_paths() -> None:
    lines = [
        _event(
            type="run.start",
            run_id="RUN-EV",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
        ),
        _event(type="test.start", test_id="t1", title="visible", file="ev.spec.ts", seq=2),
        _event(
            type="evidence",
            test_id="t1",
            evidence_kind="screenshot",
            path="evidence/t1.png",
            label="failure-shot",
            seq=3,
        ),
        _event(
            type="evidence",
            test_id="t1",
            evidence_kind="trace",
            path="evidence/t1.zip",
            label="trace",
            seq=4,
        ),
        _event(type="test.end", test_id="t1", duration_ms=200, status="failed", retries=0, seq=5),
        _event(
            type="run.end",
            run_id="RUN-EV",
            finished_at="2026-05-28T12:00:01+00:00",
            status="failed",
            tests_total=1,
            tests_failed=1,
            seq=6,
        ),
    ]

    outcome = _run_event_loop(
        aggregate_lines(lines, module_name="functional", module_id="MOD-EVAAAAAAAAAA")
    )

    [test] = outcome.tests
    assert test.evidence == ("evidence/t1.png", "evidence/t1.zip")


def test_aggregate_skips_unparseable_lines() -> None:
    lines = _run_full()
    # Inject a malformed JSON line in the middle.
    lines.insert(3, "{this-is-not-json}")
    outcome = _run_event_loop(
        aggregate_lines(lines, module_name="functional", module_id="MOD-PARSAAAAAAAA")
    )

    # Unparseable lines are skipped; aggregation still completes.
    assert outcome.module_result.metrics["tests_total"] == 2
    assert outcome.incomplete is False


def test_write_module_results_persists_envelope(tmp_path) -> None:
    artifacts = ArtifactDirectory(tmp_path)
    lines = _run_full()
    env = EnvironmentContext(
        browser="chromium",
        browser_version="bundled",
        os="Darwin-24.1",
        node_version="20.17.0",
        playwright_version="1.49.0",
    )
    outcome = _run_event_loop(
        aggregate_lines(
            lines,
            module_name="functional",
            module_id="MOD-WRITAAAAAAAA",
            environment=env,
        )
    )

    path = write_module_results(artifacts, outcome)

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert payload["module"] == "functional"
    assert payload["environment"]["browser"] == "chromium"
    assert len(payload["tests"]) == 2
    # Timestamp present and parseable.
    datetime.fromisoformat(payload["written_at"].replace("Z", "+00:00"))
