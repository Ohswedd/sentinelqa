"""Retry + flake-rate behavior tests (08.04)."""

from __future__ import annotations

import asyncio
import json

import pytest
from engine.runner.results import aggregate_lines


def _event(**fields: object) -> str:
    payload = {"schema_version": "1.0.0", "ts": "2026-05-28T12:00:00+00:00", **fields}
    return json.dumps(payload)


def _make_stream(test_id: str, attempts: list[tuple[str, int]]) -> list[str]:
    """Build a JSONL event list where ``test_id`` runs with each ``attempts``."""

    lines = [
        _event(
            type="run.start",
            run_id="RUN-RETRYXXXXX",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
            seq=1,
        ),
        _event(type="test.start", test_id=test_id, title="t", file="t.spec.ts", seq=2),
    ]
    seq = 3
    for status, duration_ms in attempts:
        lines.append(
            _event(
                type="test.end",
                test_id=test_id,
                duration_ms=duration_ms,
                status=status,
                retries=attempts.index((status, duration_ms)),
                seq=seq,
            )
        )
        seq += 1
    lines.append(
        _event(
            type="run.end",
            run_id="RUN-RETRYXXXXX",
            finished_at="2026-05-28T12:00:01+00:00",
            status="passed" if attempts[-1][0] == "passed" else "failed",
            tests_total=1,
            tests_failed=0 if attempts[-1][0] == "passed" else 1,
            seq=seq,
        )
    )
    return lines


def test_pass_on_first_attempt_is_passed_not_flaky() -> None:
    lines = _make_stream("t1", [("passed", 100)])
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-OKAAAAAAAAAA")
    )
    [test] = outcome.tests
    assert test.status == "passed"
    assert outcome.flake_rate == 0.0


def test_pass_on_retry_is_flaky() -> None:
    lines = _make_stream("t1", [("failed", 100), ("passed", 200)])
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-FLAKAAAAAAAA")
    )
    [test] = outcome.tests
    assert test.status == "flaky"
    assert outcome.flake_rate == pytest.approx(1.0)


def test_failure_after_retries_is_failed() -> None:
    lines = _make_stream("t1", [("failed", 100), ("failed", 100), ("failed", 100)])
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-FAILAAAAAAAA")
    )
    [test] = outcome.tests
    assert test.status == "failed"
    assert outcome.module_result.status == "failed"
    assert outcome.flake_rate == 0.0


def test_timeout_terminal_attempt_is_timed_out() -> None:
    lines = _make_stream("t1", [("timed_out", 30_000)])
    outcome = asyncio.run(
        aggregate_lines(lines, module_name="functional", module_id="MOD-TIMEAAAAAAAA")
    )
    [test] = outcome.tests
    assert test.status == "timed_out"
    assert outcome.module_result.status == "failed"
