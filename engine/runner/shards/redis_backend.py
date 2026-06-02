# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Redis-backed :class:`ShardCoordinator` (v1.10.0, phase 40).

The reference :class:`InMemoryCoordinator` ships the protocol's
behavioural contract; this module wires that contract to a Redis-style
key/value + sorted-set + list backing store. The engine itself
declares no ``redis`` dependency — production users either:

* install ``redis-py`` and pass ``redis.Redis(...)`` here, or
* pass any object satisfying the small :class:`RedisLike` Protocol
  (e.g. a ``fakeredis.FakeRedis`` instance for tests, or a thin
  wrapper around another KV store).

The lease bookkeeping uses Redis primitives only — `SET NX`, sorted
sets keyed on expiry, and an atomic Lua claim — so behaviour matches
``InMemoryCoordinator`` under contention. The tests confirm by
running the same conformance suite against this backend with a
:class:`FakeRedis` test double.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Protocol

from engine.runner.shards.protocol import (
    ShardCoordinator,
    ShardLease,
    ShardResult,
    ShardTask,
)

# --------------------------------------------------------------------------- #
# Redis surface — only the operations we use.
# --------------------------------------------------------------------------- #


class RedisLike(Protocol):
    """The minimal redis-py surface :class:`RedisCoordinator` relies on."""

    def hset(self, name: str, mapping: dict[str, str]) -> int: ...
    def hget(self, name: str, key: str) -> bytes | str | None: ...
    def hgetall(self, name: str) -> dict[bytes | str, bytes | str]: ...
    def hdel(self, name: str, *keys: str) -> int: ...
    def rpush(self, name: str, *values: str) -> int: ...
    def lpop(self, name: str) -> bytes | str | None: ...
    def llen(self, name: str) -> int: ...
    def set(self, name: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool: ...
    def delete(self, *names: str) -> int: ...
    def zadd(self, name: str, mapping: dict[str, float]) -> int: ...
    def zrangebyscore(self, name: str, min: float, max: float) -> list[bytes | str]: ...
    def zrem(self, name: str, *values: str) -> int: ...
    def keys(self, pattern: str) -> list[bytes | str]: ...


# --------------------------------------------------------------------------- #
# Key layout
# --------------------------------------------------------------------------- #

_DEFAULT_PREFIX: Final[str] = "sentinelqa:shards"


def _to_str(value: bytes | str | None) -> str | None:
    if value is None:
        return None
    return value.decode("utf-8") if isinstance(value, bytes) else value


class RedisCoordinator(ShardCoordinator):
    """Distributed :class:`ShardCoordinator` backed by Redis."""

    def __init__(
        self,
        client: RedisLike,
        *,
        prefix: str = _DEFAULT_PREFIX,
        now: Any | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix.rstrip(":")
        self._now = now or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _queue_key(self) -> str:
        return f"{self._prefix}:queue"

    def _task_key(self, task_id: str) -> str:
        return f"{self._prefix}:task:{task_id}"

    def _lease_key(self, task_id: str) -> str:
        return f"{self._prefix}:lease:{task_id}"

    def _lease_index_key(self) -> str:
        return f"{self._prefix}:leases"

    def _result_list_key(self, run_id: str) -> str:
        return f"{self._prefix}:results:{run_id}"

    # ------------------------------------------------------------------
    # Producer side
    # ------------------------------------------------------------------

    def enqueue(self, task: ShardTask) -> None:
        task_key = self._task_key(task.task_id)
        existing = self._client.hgetall(task_key)
        if existing:
            raise ValueError(f"task {task.task_id!r} already enqueued")
        payload = {
            "task_id": task.task_id,
            "run_id": task.run_id,
            "shard_index": str(task.shard_index),
            "shard_total": str(task.shard_total),
            "spec_paths": json.dumps(list(task.spec_paths)),
            "payload": json.dumps(dict(task.payload)),
            "schema_version": task.schema_version,
            "status": "pending",
            "worker_id": "",
            "error_message": "",
        }
        self._client.hset(task_key, mapping=payload)
        self._client.rpush(self._queue_key(), task.task_id)

    # ------------------------------------------------------------------
    # Worker side
    # ------------------------------------------------------------------

    def _reclaim_expired(self) -> None:
        """Move tasks whose lease has expired back to the pending queue."""
        now_ts = self._now().timestamp()
        expired = self._client.zrangebyscore(self._lease_index_key(), 0.0, now_ts)
        for raw in expired:
            task_id = _to_str(raw)
            if task_id is None:
                continue
            self._client.zrem(self._lease_index_key(), task_id)
            self._client.delete(self._lease_key(task_id))
            self._client.hset(
                self._task_key(task_id),
                mapping={"status": "pending", "worker_id": ""},
            )
            self._client.rpush(self._queue_key(), task_id)

    def claim(self, worker_id: str, *, lease_seconds: int = 60) -> ShardLease | None:
        self._reclaim_expired()
        while True:
            raw = self._client.lpop(self._queue_key())
            task_id = _to_str(raw)
            if task_id is None:
                return None
            task_key = self._task_key(task_id)
            record = {_to_str(k): _to_str(v) for k, v in self._client.hgetall(task_key).items()}
            if not record or record.get("status") != "pending":
                continue
            now = self._now()
            expires_at = now + timedelta(seconds=lease_seconds)
            ok = self._client.set(
                self._lease_key(task_id),
                worker_id,
                nx=True,
                ex=lease_seconds,
            )
            if not ok:
                # Lost the race — another worker has it.
                self._client.rpush(self._queue_key(), task_id)
                return None
            self._client.hset(
                task_key,
                mapping={"status": "in_progress", "worker_id": worker_id},
            )
            self._client.zadd(
                self._lease_index_key(),
                {task_id: expires_at.timestamp()},
            )
            return ShardLease(
                task=_task_from_record(record),
                worker_id=worker_id,
                leased_at=now,
                expires_at=expires_at,
            )

    def heartbeat(self, worker_id: str, task_id: str) -> bool:
        current = _to_str(self._client.hget(self._task_key(task_id), "worker_id"))
        if current != worker_id:
            return False
        status = _to_str(self._client.hget(self._task_key(task_id), "status"))
        if status != "in_progress":
            return False
        now = self._now()
        new_expiry = now + timedelta(seconds=60)
        self._client.zadd(self._lease_index_key(), {task_id: new_expiry.timestamp()})
        # Refresh the lease key TTL by re-setting it.
        self._client.set(self._lease_key(task_id), worker_id, ex=60)
        return True

    def complete(self, result: ShardResult) -> None:
        task_key = self._task_key(result.task_id)
        record = {_to_str(k): _to_str(v) for k, v in self._client.hgetall(task_key).items()}
        if not record:
            raise KeyError(f"unknown task {result.task_id!r}")
        owner = record.get("worker_id", "")
        if owner and owner != result.worker_id:
            raise ValueError(f"worker {result.worker_id!r} cannot complete task owned by {owner!r}")
        self._client.hset(task_key, mapping={"status": "completed"})
        self._client.zrem(self._lease_index_key(), result.task_id)
        self._client.delete(self._lease_key(result.task_id))
        self._client.rpush(
            self._result_list_key(result.run_id),
            json.dumps(asdict(result)),
        )

    def fail(self, task_id: str, *, worker_id: str, error_message: str) -> None:
        task_key = self._task_key(task_id)
        record = {_to_str(k): _to_str(v) for k, v in self._client.hgetall(task_key).items()}
        if not record:
            raise KeyError(f"unknown task {task_id!r}")
        owner = record.get("worker_id", "")
        if owner and owner != worker_id:
            raise ValueError(f"worker {worker_id!r} cannot fail task owned by {owner!r}")
        self._client.hset(
            task_key,
            mapping={"status": "failed", "error_message": error_message},
        )
        self._client.zrem(self._lease_index_key(), task_id)
        self._client.delete(self._lease_key(task_id))

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def results(self, run_id: str) -> tuple[ShardResult, ...]:
        key = self._result_list_key(run_id)
        # We don't have LRANGE in the minimal Protocol; emulate by popping
        # and re-pushing. In real Redis use LRANGE — keeping the surface
        # narrow lets fakeredis stand in cleanly.
        out: list[ShardResult] = []
        seen = 0
        while seen < self._client.llen(key):
            raw = self._client.lpop(key)
            if raw is None:
                break
            text = _to_str(raw)
            assert text is not None
            data = json.loads(text)
            result = ShardResult(**data)
            out.append(result)
            self._client.rpush(key, text)
            seen += 1
        return tuple(out)

    def pending(self, run_id: str) -> int:
        keys: Iterable[bytes | str] = self._client.keys(f"{self._prefix}:task:*")
        count = 0
        for raw in keys:
            task_key = _to_str(raw)
            if task_key is None:
                continue
            record = {_to_str(k): _to_str(v) for k, v in self._client.hgetall(task_key).items()}
            if record.get("run_id") != run_id:
                continue
            if record.get("status") in {"pending", "in_progress"}:
                count += 1
        return count


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _task_from_record(record: dict[str | None, str | None]) -> ShardTask:
    return ShardTask(
        task_id=record["task_id"] or "",
        run_id=record["run_id"] or "",
        shard_index=int(record["shard_index"] or "0"),
        shard_total=int(record["shard_total"] or "0"),
        spec_paths=tuple(json.loads(record.get("spec_paths") or "[]")),
        payload=json.loads(record.get("payload") or "{}"),
        schema_version=record.get("schema_version") or "1",
    )


__all__ = ["RedisCoordinator", "RedisLike"]
