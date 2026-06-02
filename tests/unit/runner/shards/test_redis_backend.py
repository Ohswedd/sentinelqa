# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Conformance tests for :class:`RedisCoordinator`.

We deliberately mirror the in-memory test surface: any new coordinator
backend must pass the same behavioural tests. ``FakeRedis`` is the
tiny in-process stand-in defined in :mod:`._fake_redis`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from engine.runner.shards import (
    ShardCoordinator,
    ShardResult,
    ShardTask,
)
from engine.runner.shards.redis_backend import RedisCoordinator

from tests.unit.runner.shards._fake_redis import FakeRedis


def _coordinator(now: datetime | None = None) -> RedisCoordinator:
    if now is None:
        return RedisCoordinator(FakeRedis())
    return RedisCoordinator(FakeRedis(), now=lambda: now)


def _task(idx: int, *, run_id: str = "RUN-XAAAAAAAAAAA") -> ShardTask:
    return ShardTask(
        task_id=f"task-{idx}",
        run_id=run_id,
        shard_index=idx,
        shard_total=4,
        spec_paths=(f"tests/foo_{idx}.spec.ts",),
        payload={"hint": f"slice-{idx}"},
    )


def _result(task: ShardTask, *, worker_id: str = "w1") -> ShardResult:
    return ShardResult(
        task_id=task.task_id,
        run_id=task.run_id,
        worker_id=worker_id,
        status="completed",
        findings_json="[]",
        module_results_json="[]",
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_shard_coordinator_protocol() -> None:
    assert isinstance(RedisCoordinator(FakeRedis()), ShardCoordinator)


def test_claim_pops_oldest_pending_task() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    coord.enqueue(_task(2))
    lease = coord.claim("worker-a")
    assert lease is not None
    assert lease.task.task_id == "task-1"


def test_claim_returns_none_when_empty() -> None:
    coord = _coordinator()
    assert coord.claim("worker-a") is None


def test_two_workers_never_get_the_same_task() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    a = coord.claim("worker-a")
    b = coord.claim("worker-b")
    assert a is not None
    assert b is None


def test_lease_expires_then_task_is_reclaimed() -> None:
    base = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
    later = base + timedelta(minutes=5)
    # Calls land in order: claim#1 reclaim, claim#1 main, claim#2 reclaim, claim#2 main.
    times = iter([base, base, later, later])
    coord = RedisCoordinator(FakeRedis(), now=lambda: next(times))
    coord.enqueue(_task(1))
    first = coord.claim("worker-a", lease_seconds=60)
    assert first is not None
    second = coord.claim("worker-b", lease_seconds=60)
    assert second is not None
    assert second.task.task_id == "task-1"
    assert second.worker_id == "worker-b"


def test_heartbeat_extends_lease() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    lease = coord.claim("worker-a", lease_seconds=60)
    assert lease is not None
    assert coord.heartbeat("worker-a", lease.task.task_id) is True


def test_heartbeat_returns_false_for_unknown_task() -> None:
    coord = _coordinator()
    assert coord.heartbeat("worker-a", "nope") is False


def test_heartbeat_rejects_wrong_worker() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    lease = coord.claim("worker-a")
    assert lease is not None
    assert coord.heartbeat("worker-b", lease.task.task_id) is False


def test_complete_records_result() -> None:
    coord = _coordinator()
    task = _task(1)
    coord.enqueue(task)
    lease = coord.claim("worker-a")
    assert lease is not None
    coord.complete(_result(task, worker_id="worker-a"))
    results = coord.results(task.run_id)
    assert len(results) == 1
    assert results[0].status == "completed"


def test_complete_rejects_wrong_worker() -> None:
    coord = _coordinator()
    task = _task(1)
    coord.enqueue(task)
    lease = coord.claim("worker-a")
    assert lease is not None
    with pytest.raises(ValueError):
        coord.complete(_result(task, worker_id="worker-b"))


def test_complete_unknown_task_raises() -> None:
    coord = _coordinator()
    with pytest.raises(KeyError):
        coord.complete(
            ShardResult(
                task_id="missing",
                run_id="RUN-XAAAAAAAAAAA",
                worker_id="w",
                status="completed",
                findings_json="[]",
                module_results_json="[]",
            )
        )


def test_fail_marks_task_failed() -> None:
    coord = _coordinator()
    task = _task(1)
    coord.enqueue(task)
    lease = coord.claim("worker-a")
    assert lease is not None
    coord.fail(task.task_id, worker_id="worker-a", error_message="oops")
    assert coord.pending(task.run_id) == 0


def test_enqueue_rejects_duplicate_task_id() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    with pytest.raises(ValueError):
        coord.enqueue(_task(1))


def test_pending_counts_pending_and_in_progress() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    coord.enqueue(_task(2))
    assert coord.pending("RUN-XAAAAAAAAAAA") == 2
    coord.claim("worker-a")
    assert coord.pending("RUN-XAAAAAAAAAAA") == 2  # still in-progress
    task = _task(1)
    coord.complete(_result(task, worker_id="worker-a"))
    assert coord.pending("RUN-XAAAAAAAAAAA") == 1


def test_results_round_trip_preserves_payload_shape() -> None:
    coord = _coordinator()
    task = _task(2)
    coord.enqueue(task)
    lease = coord.claim("worker-a")
    assert lease is not None
    coord.complete(
        ShardResult(
            task_id=task.task_id,
            run_id=task.run_id,
            worker_id="worker-a",
            status="completed",
            findings_json='[{"id":"FND-1"}]',
            module_results_json='[{"status":"passed"}]',
        )
    )
    results = coord.results(task.run_id)
    assert results[0].findings_json == '[{"id":"FND-1"}]'
    assert results[0].module_results_json == '[{"status":"passed"}]'


def test_claim_preserves_task_payload() -> None:
    coord = _coordinator()
    coord.enqueue(_task(1))
    lease = coord.claim("worker-a")
    assert lease is not None
    assert lease.task.payload == {"hint": "slice-1"}
    assert lease.task.spec_paths == ("tests/foo_1.spec.ts",)
