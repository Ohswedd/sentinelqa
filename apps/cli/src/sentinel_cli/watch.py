# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""File-watch loop for ``sentinel audit --watch``.

Re-runs the audit on file changes during local development. The goal
is to shorten the inner loop from "edit → push → CI → wait" to
"edit → terminal updates in 8 s".

The watcher polls the project tree at a short interval (200 ms by
default), debounces bursts of changes into one re-run, and ignores
generated trees (``.sentinel/``, ``node_modules/``, ``.venv/`` etc.)
so the loop never triggers on its own output.

The watcher is intentionally stdlib-only (``os.scandir`` + mtime
deltas) so we do not add a watchdog dependency for what is
fundamentally a dev-loop convenience.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DEBOUNCE_MS = 750
DEFAULT_POLL_MS = 200
DEFAULT_INCLUDE: tuple[str, ...] = (
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
    ".yaml",
    ".yml",
    ".json",
)

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".sentinel",
        ".venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        "dist",
        "build",
        "coverage",
        ".next",
        ".nuxt",
        ".turbo",
        ".cache",
    }
)


@dataclass(slots=True)
class WatchOptions:
    """Options for a watch loop. Defaults are sane for a typical web app."""

    root: Path
    debounce_ms: int = DEFAULT_DEBOUNCE_MS
    poll_ms: int = DEFAULT_POLL_MS
    include_suffixes: tuple[str, ...] = DEFAULT_INCLUDE
    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS


@dataclass(slots=True)
class WatchStats:
    """In-memory counters surfaced to the caller for testing / logging."""

    runs: int = 0
    last_run_started_at: float | None = None
    last_run_finished_at: float | None = None
    last_changed: tuple[Path, ...] = field(default_factory=tuple)


def _snapshot(opts: WatchOptions) -> dict[Path, float]:
    """Walk ``opts.root`` once and return ``{path: mtime}``."""

    snap: dict[Path, float] = {}
    for path in iter_files(opts):
        try:
            snap[path] = path.stat().st_mtime
        except OSError:
            continue
    return snap


def iter_files(opts: WatchOptions) -> Iterable[Path]:
    """Yield every file under ``opts.root`` honoring include / exclude rules."""

    suffixes = set(opts.include_suffixes)
    excludes = opts.exclude_dirs

    stack: list[Path] = [opts.root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    name = entry.name
                    # Skip dotfiles by default (editor swap files
                    # `.sw[opqr]`, `.#name#`, etc.) but let known excluded
                    # directory names through so they are skipped below.
                    if (
                        name.startswith(".")
                        and name not in (".env.example", ".gitignore")
                        and name not in excludes
                    ):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if name in excludes:
                            continue
                        stack.append(Path(entry.path))
                        continue
                    if entry.is_file(follow_symlinks=False):
                        suffix = Path(name).suffix
                        if suffix in suffixes:
                            yield Path(entry.path)
        except OSError:
            continue


def _changed_files(prev: dict[Path, float], curr: dict[Path, float]) -> tuple[Path, ...]:
    """Set-diff two snapshots and return the changed paths, sorted."""

    changed: list[Path] = []
    for path, mtime in curr.items():
        if prev.get(path) != mtime:
            changed.append(path)
    for path in prev:
        if path not in curr:
            changed.append(path)
    return tuple(sorted(set(changed)))


def watch_loop(
    opts: WatchOptions,
    run_audit: Callable[[], None],
    *,
    iterations: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    out: Callable[[str], None] | None = None,
    stats: WatchStats | None = None,
) -> WatchStats:
    """Run ``run_audit`` once, then re-run on every debounced file change.

    ``iterations`` caps the number of iterations (None = run forever).
    ``sleep`` and ``now`` are injectable so tests can drive a fake clock.
    ``out`` receives one-line status updates; pass ``None`` to suppress.
    """

    stats = stats or WatchStats()
    log = out if out is not None else (lambda _msg: None)

    log(f"[watch] watching {opts.root.resolve()} for changes (Ctrl+C to stop)")
    snapshot = _snapshot(opts)
    stats.last_run_started_at = now()
    run_audit()
    stats.runs += 1
    stats.last_run_finished_at = now()
    log("[watch] initial audit done; waiting for changes")

    iteration = 0
    while iterations is None or iteration < iterations:
        iteration += 1
        sleep(opts.poll_ms / 1000.0)
        new_snapshot = _snapshot(opts)
        changed = _changed_files(snapshot, new_snapshot)
        snapshot = new_snapshot
        if not changed:
            continue

        # Debounce — keep collecting changes until they stop.
        debounce_seconds = opts.debounce_ms / 1000.0
        deadline = now() + debounce_seconds
        while now() < deadline:
            sleep(opts.poll_ms / 1000.0)
            even_newer = _snapshot(opts)
            more = _changed_files(snapshot, even_newer)
            if more:
                changed = tuple(sorted(set(changed) | set(more)))
                deadline = now() + debounce_seconds
            snapshot = even_newer

        stats.last_changed = changed
        log(_format_change_summary(changed, opts.root))
        stats.last_run_started_at = now()
        run_audit()
        stats.runs += 1
        stats.last_run_finished_at = now()
        log("[watch] audit done; waiting for changes")

    return stats


def _format_change_summary(changed: tuple[Path, ...], root: Path) -> str:
    """Render one human-friendly line describing what changed."""

    try:
        root_resolved = root.resolve()
    except OSError:
        root_resolved = root
    samples: list[str] = []
    for path in changed[:3]:
        try:
            rel = str(path.resolve().relative_to(root_resolved))
        except (OSError, ValueError):
            rel = str(path)
        samples.append(rel)
    suffix = "" if len(changed) <= 3 else f" (+{len(changed) - 3} more)"
    return f"[watch] {len(changed)} file(s) changed: {', '.join(samples)}{suffix}"


def emit_to_stderr(message: str) -> None:
    """Default printer used by the audit command — stderr keeps stdout clean."""

    sys.stderr.write(message + "\n")
    sys.stderr.flush()


__all__ = [
    "DEFAULT_DEBOUNCE_MS",
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_INCLUDE",
    "DEFAULT_POLL_MS",
    "WatchOptions",
    "WatchStats",
    "emit_to_stderr",
    "iter_files",
    "watch_loop",
]
