"""Deterministic shard splitting + merge tests (08.03)."""

from __future__ import annotations

import asyncio
import json

import pytest
from engine.runner.results import (
    EnvironmentContext,
    aggregate_lines,
)
from engine.runner.sharding import (
    ShardSpec,
    merge_outcomes,
    split_shard,
)


def test_shard_spec_parses() -> None:
    spec = ShardSpec.parse("2/5")
    assert spec.current == 2
    assert spec.total == 5


def test_shard_spec_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        ShardSpec(current=0, total=1)
    with pytest.raises(ValueError):
        ShardSpec(current=3, total=2)
    with pytest.raises(ValueError):
        ShardSpec.parse("not-a-shard")


def test_split_shard_covers_every_file_with_no_overlap() -> None:
    spec_files = [
        "tests/sentinel/login.spec.ts",
        "tests/sentinel/signup.spec.ts",
        "tests/sentinel/crud.spec.ts",
        "tests/sentinel/admin.spec.ts",
        "tests/sentinel/payment.spec.ts",
        "tests/sentinel/role.spec.ts",
        "tests/sentinel/a11y.spec.ts",
        "tests/sentinel/perf.spec.ts",
    ]

    total = 3
    covered: list[str] = []
    for current in range(1, total + 1):
        subset = split_shard(spec_files, ShardSpec(current=current, total=total))
        covered.extend(subset)

    assert sorted(covered) == sorted(spec_files)
    assert len(covered) == len(set(covered))  # no overlap


def test_split_shard_is_stable_across_runs() -> None:
    spec_files = [f"tests/sentinel/file-{i}.spec.ts" for i in range(50)]
    first = split_shard(spec_files, ShardSpec(current=1, total=5))
    second = split_shard(spec_files, ShardSpec(current=1, total=5))
    assert first == second


def _run_full(test_ids: list[str], statuses: list[str]) -> list[str]:
    events: list[dict[str, object]] = [
        {
            "type": "run.start",
            "run_id": "RUN-SHARDXXXXX",
            "target": "http://localhost",
            "started_at": "2026-05-28T12:00:00+00:00",
        },
    ]
    seq = 1
    for tid, status in zip(test_ids, statuses, strict=True):
        events.append(
            {
                "type": "test.start",
                "test_id": tid,
                "title": tid,
                "file": f"{tid}.spec.ts",
            }
        )
        events.append(
            {
                "type": "test.end",
                "test_id": tid,
                "duration_ms": 200,
                "status": status,
                "retries": 0,
            }
        )
    events.append(
        {
            "type": "run.end",
            "run_id": "RUN-SHARDXXXXX",
            "finished_at": "2026-05-28T12:00:10+00:00",
            "status": "passed" if all(s == "passed" for s in statuses) else "failed",
            "tests_total": len(test_ids),
            "tests_failed": sum(1 for s in statuses if s in {"failed", "timed_out"}),
        }
    )
    lines: list[str] = []
    for i, ev in enumerate(events, start=1):
        ev["schema_version"] = "1.0.0"
        ev["seq"] = seq + i - 1
        ev["ts"] = "2026-05-28T12:00:00+00:00"
        lines.append(json.dumps(ev))
    return lines


def test_merge_outcomes_combines_two_shards() -> None:
    shard1_lines = _run_full(["t1", "t2"], ["passed", "passed"])
    shard2_lines = _run_full(["t3", "t4"], ["passed", "failed"])
    env = EnvironmentContext(
        browser="chromium",
        browser_version="bundled",
        os="Darwin",
    )

    outcome1 = asyncio.run(
        aggregate_lines(
            shard1_lines, module_name="functional", module_id="MOD-S1AAAAAAAAAA", environment=env
        )
    )
    outcome2 = asyncio.run(
        aggregate_lines(
            shard2_lines, module_name="functional", module_id="MOD-S2AAAAAAAAAA", environment=env
        )
    )

    merged = merge_outcomes([outcome1, outcome2], module_name="functional")

    assert {t.test_id for t in merged.tests} == {"t1", "t2", "t3", "t4"}
    assert merged.module_result.metrics["tests_total"] == 4
    assert merged.module_result.metrics["tests_failed"] == 1
    assert merged.module_result.status == "failed"


def test_merge_outcomes_status_is_worst_of() -> None:
    incomplete_lines = _run_full(["t1"], ["passed"])[:-1]  # drop run.end
    full_lines = _run_full(["t2"], ["passed"])

    incomplete = asyncio.run(
        aggregate_lines(incomplete_lines, module_name="functional", module_id="MOD-INAAAAAAAAAA")
    )
    passed = asyncio.run(
        aggregate_lines(full_lines, module_name="functional", module_id="MOD-OKAAAAAAAAAA")
    )

    merged = merge_outcomes([passed, incomplete], module_name="functional")
    assert merged.module_result.status == "incomplete"


def test_merge_outcomes_requires_at_least_one() -> None:
    with pytest.raises(ValueError):
        merge_outcomes([], module_name="functional")
