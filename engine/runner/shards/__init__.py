# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Distributed shard protocol (v1.8.0, phase 38).

The local sharding logic in :mod:`engine.runner.sharding` lets a single
host split a spec list into ``N`` independent slices. The distributed
extension here lets those slices land on different machines and report
back through a shared coordinator.

The user holds the contract: SentinelQA defines the Protocols
(:class:`ShardCoordinator`, :class:`ShardWorker`, plus the
:class:`ShardTask` / :class:`ShardResult` payloads) and ships an
in-memory reference implementation (:class:`InMemoryCoordinator`).
Real-world deployments wire the Protocols to a job queue — Redis,
Postgres NOTIFY, SQS, etc. — without modifying engine code.

Key contracts:

* Tasks are claimed exclusively. A coordinator that hands the same
  task to two workers violates the contract; results must converge.
* Workers are stateless. A worker that crashes mid-task must be safe
  to restart; the coordinator re-issues tasks whose lease has expired.
* Results carry the shard's typed findings + module results plus a
  ``schema_version`` so heterogeneous workers can roll forward.

This module ships no network code. Wiring the Protocols to Redis,
Postgres, or your queue of choice is intentionally out-of-tree.
"""

from __future__ import annotations

from engine.runner.shards.in_memory import InMemoryCoordinator
from engine.runner.shards.protocol import (
    SHARD_PROTOCOL_VERSION,
    ShardCoordinator,
    ShardLease,
    ShardResult,
    ShardStatus,
    ShardTask,
    ShardWorker,
)
from engine.runner.shards.redis_backend import RedisCoordinator, RedisLike

__all__ = [
    "InMemoryCoordinator",
    "RedisCoordinator",
    "RedisLike",
    "SHARD_PROTOCOL_VERSION",
    "ShardCoordinator",
    "ShardLease",
    "ShardResult",
    "ShardStatus",
    "ShardTask",
    "ShardWorker",
]
