"""End-to-end partial-stream behavior (08.05).

A real run can be interrupted at any of these boundaries:

 1. Mid-test (we see test.start but no test.end).
 2. Mid-attempt (we see one test.end but the retry never fires).
 3. Mid-stream (we see test.end but no run.end).

In every case the aggregator must produce a deterministic outcome — no
exceptions escape, and the resulting status carries enough information
for the Analyzer to triage.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from engine.orchestrator.artifacts import ArtifactDirectory
from engine.runner.results import aggregate_lines, write_module_results


def _line(**fields: object) -> str:
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "seq": fields.pop("seq", 1),
            "ts": "2026-05-28T12:00:00+00:00",
            **fields,
        }
    )


def _run() -> list[str]:
    return [
        _line(
            type="run.start",
            run_id="RUN-PARTAAAAAAAA",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
            seq=1,
        ),
        _line(type="test.start", test_id="t1", title="login", file="login.spec.ts", seq=2),
        _line(type="test.end", test_id="t1", duration_ms=400, status="passed", retries=0, seq=3),
        _line(type="test.start", test_id="t2", title="signup", file="signup.spec.ts", seq=4),
        _line(type="test.end", test_id="t2", duration_ms=900, status="failed", retries=0, seq=5),
        _line(
            type="run.end",
            run_id="RUN-PARTAAAAAAAA",
            finished_at="2026-05-28T12:00:30+00:00",
            status="failed",
            tests_total=2,
            tests_failed=1,
            seq=6,
        ),
    ]


def test_interrupted_after_test_start_records_skipped(tmp_path: Path) -> None:
    lines = [_run()[0], _run()[1]]  # run.start + test.start, nothing else

    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-MIDAAAAAAAAA")
    )

    assert outcome.module_result.status == "incomplete"
    # The test that never finished should be visible as skipped (the
    # accumulator initializes to skipped until test.end fires).
    assert any(t.status == "skipped" for t in outcome.tests)


def test_interrupted_after_test_end_records_partial(tmp_path: Path) -> None:
    lines = _run()[:-1]  # everything except run.end

    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-PARTAAAAAAAA")
    )

    assert outcome.module_result.status == "incomplete"
    # Both tests have status from their test.end events.
    statuses = sorted(t.status for t in outcome.tests)
    assert "failed" in statuses
    assert "passed" in statuses


def test_partial_stream_writes_module_results_artifact(tmp_path: Path) -> None:
    lines = _run()[:-2]  # interrupted before t2.end
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-ARTAAAAAAAAA")
    )
    artifacts = ArtifactDirectory(tmp_path)
    target = write_module_results(artifacts, outcome)
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["incomplete"] is True
    assert payload["module_result"]["status"] == "incomplete"
