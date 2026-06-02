# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Distributed shard protocol — Protocols, payloads, version pin."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal, Protocol, runtime_checkable

SHARD_PROTOCOL_VERSION: Final[str] = "1"

ShardStatus = Literal["pending", "in_progress", "completed", "failed", "lost"]


@dataclass(frozen=True, slots=True)
class ShardTask:
    """One slice of work the coordinator hands out.

    ``run_id`` and ``shard_index`` / ``shard_total`` together identify
    the slice deterministically. ``spec_paths`` is the list of test-spec
    paths the worker should execute; for non-spec workloads (discovery,
    a11y) the payload may carry route URLs instead.

    ``payload`` is a free-form mapping that the engine doesn't peek at.
    Queue-specific implementations attach their own metadata (Redis
    stream id, SQS receipt handle) without changing the engine contract.
    """

    task_id: str
    run_id: str
    shard_index: int
    shard_total: int
    spec_paths: tuple[str, ...] = field(default_factory=tuple)
    payload: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = SHARD_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.shard_index < 1 or self.shard_total < 1:
            raise ValueError(f"shard {self.shard_index}/{self.shard_total}: indices must be >= 1")
        if self.shard_index > self.shard_total:
            raise ValueError(f"shard {self.shard_index}/{self.shard_total}: index > total")


@dataclass(frozen=True, slots=True)
class ShardLease:
    """Exclusive ownership of a :class:`ShardTask`.

    Workers must call :meth:`ShardCoordinator.heartbeat` before
    ``expires_at`` or the coordinator will reissue the task.
    Leases are intentionally short (default 60 s in the in-memory
    reference impl) so a crashed worker doesn't stall a run.
    """

    task: ShardTask
    worker_id: str
    leased_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ShardResult:
    """Worker → coordinator: outcome of a single task.

    ``findings_json`` and ``module_results_json`` are serialised JSON
    payloads (not parsed) so the coordinator can ship them across
    machines without depending on the engine's domain models. The
    receiving end deserialises against ``schema_version``.
    """

    task_id: str
    run_id: str
    worker_id: str
    status: ShardStatus
    findings_json: str
    module_results_json: str
    error_message: str = ""
    schema_version: str = SHARD_PROTOCOL_VERSION


@runtime_checkable
class ShardCoordinator(Protocol):
    """The queue-side contract.

    Implementations bind this Protocol to a backing store: Redis Streams,
    Postgres ``LISTEN/NOTIFY``, SQS, an in-memory mutex (the reference
    impl), etc. The engine talks to the Protocol exclusively.
    """

    def enqueue(self, task: ShardTask) -> None:
        """Make ``task`` available to be claimed by a worker."""

    def claim(self, worker_id: str, *, lease_seconds: int = 60) -> ShardLease | None:
        """Atomically claim the next pending task.

        Returns ``None`` when no work is available. The lease is
        exclusive: until it expires, no other worker may claim the
        same task.
        """

    def heartbeat(self, worker_id: str, task_id: str) -> bool:
        """Extend an active lease. Returns False if the lease was lost."""

    def complete(self, result: ShardResult) -> None:
        """Submit a successful result; the task transitions to completed."""

    def fail(self, task_id: str, *, worker_id: str, error_message: str) -> None:
        """Mark the task failed. The coordinator may requeue it."""

    def results(self, run_id: str) -> tuple[ShardResult, ...]:
        """Return every result recorded for ``run_id`` so far."""

    def pending(self, run_id: str) -> int:
        """Number of tasks that are still pending or in-progress."""


@runtime_checkable
class ShardWorker(Protocol):
    """The worker-side contract.

    A worker pulls a task from the coordinator, runs it, and reports
    back. The engine ships no concrete worker implementation; users
    glue their local runner / Docker runner / cloud sandbox to this
    Protocol.
    """

    worker_id: str

    def execute(self, lease: ShardLease) -> ShardResult:
        """Run the task body and return the result.

        Implementations should call ``coordinator.heartbeat`` from a
        background thread for long-running tasks.
        """


__all__ = [
    "SHARD_PROTOCOL_VERSION",
    "ShardCoordinator",
    "ShardLease",
    "ShardResult",
    "ShardStatus",
    "ShardTask",
    "ShardWorker",
]
