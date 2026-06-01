# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Disk-backed, namespaced byte cache used by the run lifecycle.

The store lives under ``.sentinel/cache/`` by default and is structured
as ``<root>/<namespace>/<aa>/<remaining>.bin`` so a single namespace
holding tens of thousands of entries does not produce a directory the
operating system struggles to scandir.

All public methods are thread-safe at the file-write boundary: writes
go through ``os.replace`` of a temp file so a partial write never
becomes visible to a concurrent reader. The store is intentionally
content-agnostic — values are bytes and the caller owns serialisation.
"""

from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

_NAMESPACE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


class CacheError(ValueError):
    """Raised when an invalid namespace or key is supplied."""


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Lightweight stats useful for reporting / tests."""

    entries: int
    bytes: int


class CacheStore:
    """A namespaced, content-addressed byte cache."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def _validate(self, namespace: str, key: str) -> None:
        if not _NAMESPACE_RE.match(namespace):
            raise CacheError(f"namespace must match {_NAMESPACE_RE.pattern!r}; got {namespace!r}")
        if not _KEY_RE.match(key):
            raise CacheError(f"key must match {_KEY_RE.pattern!r}; got {key!r}")

    def path_for(self, namespace: str, key: str) -> Path:
        """Compute the absolute on-disk path for a (namespace, key) pair."""

        self._validate(namespace, key)
        if len(key) < 2:
            shard, rest = key, ""
        else:
            shard, rest = key[:2], key[2:]
        return self._root / namespace / shard / f"{rest or '_'}.bin"

    def has(self, namespace: str, key: str) -> bool:
        return self.path_for(namespace, key).is_file()

    def get(self, namespace: str, key: str) -> bytes | None:
        path = self.path_for(namespace, key)
        if not path.is_file():
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def put(self, namespace: str, key: str, value: bytes) -> Path:
        """Atomically write ``value`` and return the resulting path."""

        path = self.path_for(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_bytes(value)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                with contextlib.suppress(OSError):
                    tmp.unlink()
        return path

    def delete(self, namespace: str, key: str) -> bool:
        path = self.path_for(namespace, key)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

    def stats(self, namespace: str) -> CacheStats:
        """Walk ``namespace`` and return basic stats."""

        if not _NAMESPACE_RE.match(namespace):
            raise CacheError(f"bad namespace: {namespace!r}")
        ns_root = self._root / namespace
        if not ns_root.is_dir():
            return CacheStats(entries=0, bytes=0)
        entries = 0
        total = 0
        for shard in ns_root.iterdir():
            if not shard.is_dir():
                continue
            for file in shard.iterdir():
                if file.suffix == ".bin":
                    entries += 1
                    try:
                        total += file.stat().st_size
                    except OSError:
                        continue
        return CacheStats(entries=entries, bytes=total)


def default_cache_root(project_root: Path | None = None) -> Path:
    """Resolve the conventional cache location: ``.sentinel/cache/``."""

    base = project_root or Path.cwd()
    return base / ".sentinel" / "cache"


__all__ = ["CacheError", "CacheStats", "CacheStore", "default_cache_root"]
