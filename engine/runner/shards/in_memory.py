# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""In-memory reference implementation of :class:`ShardCoordinator`.

Useful for:

* unit-testing the Protocol contract without a real queue,
* single-host runs that still want to exercise the shard wire format,
* a smoke target for new queue backends (run the same test suite
  against the new backend; behaviour must match this reference).

Thread-safe; one process only. Production deployments must back the
Protocol with a network queue (Redis Streams, Postgres NOTIFY, etc.).
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from engine.runner.shards.protocol import (
    ShardCoordinator,
    ShardLease,
    ShardResult,
    ShardStatus,
    ShardTask,
)


@dataclass
class _TaskState:
    task: ShardTask
    status: ShardStatus
    worker_id: str = ""
    leased_until: datetime | None = None
    error_message: str = ""


class InMemoryCoordinator(ShardCoordinator):
    """Reference :class:`ShardCoordinator` backed by a process-local dict."""

    def __init__(self, *, now: callable[[], datetime] | None = None) -> None:  # type: ignore[valid-type]
        self._lock = threading.RLock()
        self._tasks: dict[str, _TaskState] = {}
        self._queue: deque[str] = deque()
        self._results: dict[str, list[ShardResult]] = {}
        self._now = now or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Producer side
    # ------------------------------------------------------------------

    def enqueue(self, task: ShardTask) -> None:
        with self._lock:
            if task.task_id in self._tasks:
                raise ValueError(f"task {task.task_id!r} already enqueued")
            self._tasks[task.task_id] = _TaskState(task=task, status="pending")
            self._queue.append(task.task_id)

    # ------------------------------------------------------------------
    # Worker side
    # ------------------------------------------------------------------

    def _reclaim_expired_locked(self) -> None:
        now = self._now()
        for state in self._tasks.values():
            if (
                state.status == "in_progress"
                and state.leased_until is not None
                and state.leased_until < now
            ):
                state.status = "pending"
                state.worker_id = ""
                state.leased_until = None
                self._queue.append(state.task.task_id)

    def claim(self, worker_id: str, *, lease_seconds: int = 60) -> ShardLease | None:
        with self._lock:
            self._reclaim_expired_locked()
            while self._queue:
                task_id = self._queue.popleft()
                state = self._tasks.get(task_id)
                if state is None or state.status != "pending":
                    continue
                leased_at = self._now()
                expires_at = leased_at + timedelta(seconds=lease_seconds)
                state.status = "in_progress"
                state.worker_id = worker_id
                state.leased_until = expires_at
                return ShardLease(
                    task=state.task,
                    worker_id=worker_id,
                    leased_at=leased_at,
                    expires_at=expires_at,
                )
            return None

    def heartbeat(self, worker_id: str, task_id: str) -> bool:
        with self._lock:
            state = self._tasks.get(task_id)
            if state is None or state.worker_id != worker_id:
                return False
            if state.status != "in_progress":
                return False
            now = self._now()
            if state.leased_until is None or state.leased_until < now:
                state.status = "lost"
                return False
            state.leased_until = now + timedelta(seconds=60)
            return True

    def complete(self, result: ShardResult) -> None:
        with self._lock:
            state = self._tasks.get(result.task_id)
            if state is None:
                raise KeyError(f"unknown task {result.task_id!r}")
            if state.worker_id and state.worker_id != result.worker_id:
                raise ValueError(
                    f"worker {result.worker_id!r} cannot complete task owned by "
                    f"{state.worker_id!r}"
                )
            state.status = "completed"
            self._results.setdefault(result.run_id, []).append(result)

    def fail(self, task_id: str, *, worker_id: str, error_message: str) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                raise KeyError(f"unknown task {task_id!r}")
            if state.worker_id and state.worker_id != worker_id:
                raise ValueError(
                    f"worker {worker_id!r} cannot fail task owned by {state.worker_id!r}"
                )
            state.status = "failed"
            state.error_message = error_message

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def results(self, run_id: str) -> tuple[ShardResult, ...]:
        with self._lock:
            return tuple(self._results.get(run_id, ()))

    def pending(self, run_id: str) -> int:
        with self._lock:
            return sum(
                1
                for state in self._tasks.values()
                if state.task.run_id == run_id and state.status in {"pending", "in_progress"}
            )


__all__ = ["InMemoryCoordinator"]
