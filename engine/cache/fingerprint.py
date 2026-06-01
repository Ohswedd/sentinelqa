# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Deterministic content fingerprint of a project's source tree.

A :class:`SourceFingerprint` is a sha256 digest computed over the sorted
(relative-path, file-content-hash) pairs of every file under the project
root that:

* lives outside the documented exclude directories
  (``node_modules``, ``.git``, ``.venv``, build trees, the cache itself);
* has a suffix in :data:`DEFAULT_INCLUDE_SUFFIXES` (the source surface
  the audit actually cares about — code, templates, configs, lockfiles).

Two trees with identical content produce identical hashes regardless of
mtime, ordering, or absolute path. This invariant is the foundation for
the discovery cache, the plan cache, and ``sentinel audit --since``.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_BUFFER = 64 * 1024

DEFAULT_INCLUDE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".vue",
        ".svelte",
        ".html",
        ".css",
        ".scss",
        ".md",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".lock",
    }
)

DEFAULT_INCLUDE_BASENAMES: Final[frozenset[str]] = frozenset(
    {
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package-lock.json",
        "pyproject.toml",
        "uv.lock",
        "Pipfile.lock",
        "requirements.txt",
        "requirements.lock",
        "Dockerfile",
        "Makefile",
    }
)

DEFAULT_EXCLUDE_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".sentinel",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".turbo",
        ".cache",
        ".parcel-cache",
        "coverage",
        ".coverage",
        ".tox",
    }
)


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """Content-addressed identity of a project source tree.

    ``hash`` is a hex sha256 — the canonical key for cache lookup and
    ``--since`` comparison. ``file_count`` and ``total_bytes`` are
    informational and surface in run.json for observability.
    """

    hash: str
    file_count: int
    total_bytes: int

    def short(self) -> str:
        """Return the leading 12 characters — sufficient for display."""

        return self.hash[:12]


def _hash_file(path: Path) -> tuple[str, int]:
    """Return ``(sha256_hex, byte_size)`` for one file.

    Streams the read in 64 KiB chunks so the cost is bounded for
    arbitrarily-large lockfiles or generated artefacts.
    """

    h = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while chunk := fh.read(_BUFFER):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _is_included(name: str, suffixes: frozenset[str], basenames: frozenset[str]) -> bool:
    if name in basenames:
        return True
    dot = name.rfind(".")
    if dot == -1:
        return False
    return name[dot:].lower() in suffixes


def _iter_source_files(
    root: Path,
    *,
    include_suffixes: frozenset[str],
    include_basenames: frozenset[str],
    exclude_dirs: frozenset[str],
) -> list[Path]:
    """Walk ``root`` and yield every included file path (sorted)."""

    out: list[Path] = []
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            try:
                if entry.is_dir(follow_symlinks=False):
                    if name in exclude_dirs:
                        continue
                    stack.append(Path(entry.path))
                    continue
                if entry.is_file(follow_symlinks=False) and _is_included(
                    name, include_suffixes, include_basenames
                ):
                    out.append(Path(entry.path))
            except OSError:
                continue
    out.sort()
    return out


def compute_fingerprint(
    root: Path,
    *,
    include_suffixes: frozenset[str] | None = None,
    include_basenames: frozenset[str] | None = None,
    exclude_dirs: frozenset[str] | None = None,
) -> SourceFingerprint:
    """Compute a deterministic fingerprint of the source tree at ``root``.

    The hash includes the relative POSIX path of each file (so renames
    invalidate the cache) and the sha256 of each file's content. Path
    separators are normalised to ``/`` so a tree fingerprinted on
    Windows and macOS yields the same digest.
    """

    suffixes = include_suffixes or DEFAULT_INCLUDE_SUFFIXES
    basenames = include_basenames or DEFAULT_INCLUDE_BASENAMES
    excludes = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    root_resolved = root.resolve()
    files = _iter_source_files(
        root_resolved,
        include_suffixes=suffixes,
        include_basenames=basenames,
        exclude_dirs=excludes,
    )
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        file_hash, file_size = _hash_file(path)
        rel = path.relative_to(root_resolved).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
        total_bytes += file_size
    return SourceFingerprint(
        hash=digest.hexdigest(),
        file_count=len(files),
        total_bytes=total_bytes,
    )


__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_INCLUDE_BASENAMES",
    "DEFAULT_INCLUDE_SUFFIXES",
    "SourceFingerprint",
    "compute_fingerprint",
]
