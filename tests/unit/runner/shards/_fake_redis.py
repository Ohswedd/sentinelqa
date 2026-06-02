# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""A tiny in-process implementation of the :class:`RedisLike` Protocol.

Used by the conformance tests to exercise
:class:`engine.runner.shards.redis_backend.RedisCoordinator` without a
real Redis server. The semantics match the subset of Redis commands
the coordinator uses (no TTL expiry simulation — leases are reclaimed
by the coordinator's clock-based ``zrangebyscore`` sweep).
"""

from __future__ import annotations

from collections import defaultdict, deque


class FakeRedis:
    """Minimal Redis stand-in."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self._lists: dict[str, deque[str]] = defaultdict(deque)
        self._strings: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = defaultdict(dict)

    # ----- hash --------------------------------------------------------

    def hset(self, name: str, mapping: dict[str, str]) -> int:
        bucket = self._hashes[name]
        added = 0
        for k, v in mapping.items():
            if k not in bucket:
                added += 1
            bucket[k] = v
        return added

    def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._hashes.get(name, {}))

    def hdel(self, name: str, *keys: str) -> int:
        bucket = self._hashes.get(name)
        if bucket is None:
            return 0
        removed = 0
        for key in keys:
            if key in bucket:
                del bucket[key]
                removed += 1
        return removed

    # ----- list --------------------------------------------------------

    def rpush(self, name: str, *values: str) -> int:
        for v in values:
            self._lists[name].append(v)
        return len(self._lists[name])

    def lpop(self, name: str) -> str | None:
        bucket = self._lists.get(name)
        if not bucket:
            return None
        return bucket.popleft()

    def llen(self, name: str) -> int:
        return len(self._lists.get(name, ()))

    # ----- string ------------------------------------------------------

    def set(self, name: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        del ex  # FakeRedis ignores TTL — leases swept by zset score.
        if nx and name in self._strings:
            return False
        self._strings[name] = value
        return True

    def delete(self, *names: str) -> int:
        removed = 0
        for n in names:
            if n in self._strings:
                del self._strings[n]
                removed += 1
            if n in self._hashes:
                del self._hashes[n]
                removed += 1
            if n in self._lists:
                del self._lists[n]
                removed += 1
            if n in self._zsets:
                del self._zsets[n]
                removed += 1
        return removed

    # ----- sorted set --------------------------------------------------

    def zadd(self, name: str, mapping: dict[str, float]) -> int:
        added = 0
        for k, v in mapping.items():
            if k not in self._zsets[name]:
                added += 1
            self._zsets[name][k] = v
        return added

    def zrangebyscore(self, name: str, min: float, max: float) -> list[str]:
        entries = self._zsets.get(name, {})
        return [k for k, score in entries.items() if min <= score <= max]

    def zrem(self, name: str, *values: str) -> int:
        bucket = self._zsets.get(name)
        if bucket is None:
            return 0
        removed = 0
        for v in values:
            if v in bucket:
                del bucket[v]
                removed += 1
        return removed

    # ----- keys --------------------------------------------------------

    def keys(self, pattern: str) -> list[str]:
        suffix_glob = pattern.endswith("*")
        prefix = pattern[:-1] if suffix_glob else pattern
        out: list[str] = []
        seen: set[str] = set()
        for k in (*self._hashes, *self._lists, *self._strings, *self._zsets):
            if k in seen:
                continue
            seen.add(k)
            if suffix_glob:
                if k.startswith(prefix):
                    out.append(k)
            elif k == pattern:
                out.append(k)
        return out
