# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the disk-backed cache store."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.cache.store import (
    CacheError,
    CacheStats,
    CacheStore,
    default_cache_root,
)


def test_put_then_get_round_trip(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    payload = b'{"hello": "world"}'
    store.put("discovery", "abc123def456", payload)
    assert store.get("discovery", "abc123def456") == payload


def test_get_missing_returns_none(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    assert store.get("discovery", "nonexistent") is None


def test_has_reflects_presence(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    assert store.has("plan", "k1") is False
    store.put("plan", "k1", b"x")
    assert store.has("plan", "k1") is True


def test_delete_removes_entry(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.put("plan", "k1", b"x")
    assert store.delete("plan", "k1") is True
    assert store.has("plan", "k1") is False
    assert store.delete("plan", "k1") is False


def test_put_overwrites_existing_entry(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.put("ns", "k", b"first")
    store.put("ns", "k", b"second")
    assert store.get("ns", "k") == b"second"


def test_path_for_shards_keys_by_first_two_chars(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    path = store.path_for("discovery", "abcdef")
    assert path == tmp_path / "discovery" / "ab" / "cdef.bin"


def test_path_for_handles_short_keys(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    path = store.path_for("ns", "ab")
    assert path == tmp_path / "ns" / "ab" / "_.bin"


def test_path_for_rejects_invalid_namespace(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    with pytest.raises(CacheError):
        store.path_for("Bad Name", "k")
    with pytest.raises(CacheError):
        store.path_for("", "k")
    with pytest.raises(CacheError):
        store.path_for("../escape", "k")


def test_path_for_rejects_invalid_key(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    with pytest.raises(CacheError):
        store.path_for("ns", "../escape")
    with pytest.raises(CacheError):
        store.path_for("ns", "")
    with pytest.raises(CacheError):
        store.path_for("ns", "bad space")


def test_stats_reports_entry_count_and_bytes(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.put("ns", "k1", b"x" * 10)
    store.put("ns", "k2", b"y" * 20)
    stats = store.stats("ns")
    assert isinstance(stats, CacheStats)
    assert stats.entries == 2
    assert stats.bytes == 30


def test_stats_returns_zero_when_namespace_missing(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    stats = store.stats("never-used")
    assert stats.entries == 0
    assert stats.bytes == 0


def test_atomic_put_via_temp_file(tmp_path: Path) -> None:
    """``put`` must not leave a ``.tmp`` file behind on success."""

    store = CacheStore(tmp_path)
    store.put("ns", "k", b"payload")
    leftovers = list(tmp_path.rglob("*.tmp"))
    assert leftovers == []


def test_default_cache_root_under_dotsentinel(tmp_path: Path) -> None:
    root = default_cache_root(tmp_path)
    assert root == tmp_path / ".sentinel" / "cache"
