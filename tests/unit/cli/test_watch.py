# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the file-watch loop used by ``sentinel audit --watch``."""

from __future__ import annotations

from pathlib import Path

from sentinel_cli.watch import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_INCLUDE,
    WatchOptions,
    WatchStats,
    iter_files,
    watch_loop,
)


def _write(path: Path, body: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _drain_until_runs(opts: WatchOptions, target_runs: int) -> WatchStats:
    """Helper: run the loop, counting iterations, until ``target_runs`` runs."""

    runs: list[int] = []

    def _audit() -> None:
        runs.append(1)

    stats = WatchStats()
    fake_clock = [0.0]

    def _sleep(_seconds: float) -> None:
        fake_clock[0] += 0.01

    def _now() -> float:
        return fake_clock[0]

    return watch_loop(
        opts,
        _audit,
        iterations=target_runs * 10,
        sleep=_sleep,
        now=_now,
        stats=stats,
    )


def test_iter_files_returns_only_known_suffixes(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "main.py")
    _write(tmp_path / "src" / "app.ts")
    _write(tmp_path / "README.md")  # ignored — not in DEFAULT_INCLUDE
    _write(tmp_path / "image.png")  # ignored
    opts = WatchOptions(root=tmp_path)
    found = {p.name for p in iter_files(opts)}
    assert "main.py" in found
    assert "app.ts" in found
    assert "README.md" not in found
    assert "image.png" not in found


def test_iter_files_skips_excluded_directories(tmp_path: Path) -> None:
    _write(tmp_path / "node_modules" / "lib" / "x.js")
    _write(tmp_path / ".venv" / "site-packages" / "y.py")
    _write(tmp_path / "src" / "real.py")
    opts = WatchOptions(root=tmp_path)
    found = {p.name for p in iter_files(opts)}
    assert "real.py" in found
    assert "x.js" not in found
    assert "y.py" not in found


def test_watch_loop_runs_audit_once_on_start(tmp_path: Path) -> None:
    _write(tmp_path / "main.py")
    runs: list[int] = []
    fake_clock = [0.0]

    def _audit() -> None:
        runs.append(1)

    stats = WatchStats()
    watch_loop(
        WatchOptions(root=tmp_path),
        _audit,
        iterations=0,
        sleep=lambda _s: None,
        now=lambda: fake_clock[0],
        stats=stats,
    )
    assert runs == [1]
    assert stats.runs == 1
    assert stats.last_run_started_at is not None
    assert stats.last_run_finished_at is not None


def test_watch_loop_reacts_to_a_change(tmp_path: Path) -> None:
    target = _write(tmp_path / "main.py")
    runs: list[int] = []
    fake_clock = [0.0]

    def _audit() -> None:
        runs.append(1)
        # After first audit, mutate the watched file.
        if len(runs) == 1:
            target.write_text("changed\n", encoding="utf-8")
            # bump mtime forward in case the test runs faster than fs resolution
            import os as _os

            _os.utime(target, (10.0, 10.0))

    def _sleep(_s: float) -> None:
        fake_clock[0] += 1.0  # large step so debounce expires fast

    stats = WatchStats()
    watch_loop(
        WatchOptions(root=tmp_path, debounce_ms=10, poll_ms=10),
        _audit,
        iterations=3,
        sleep=_sleep,
        now=lambda: fake_clock[0],
        stats=stats,
    )
    assert stats.runs >= 2, f"expected ≥ 2 runs, got {stats.runs}"


def test_default_include_covers_common_web_extensions() -> None:
    """The default include list must cover the everyday web stack."""

    for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"):
        assert ext in DEFAULT_INCLUDE


def test_default_exclude_covers_common_generated_trees() -> None:
    """The exclude set must keep us out of node_modules / .venv / build."""

    for d in ("node_modules", ".venv", ".git", "dist", "build", ".sentinel"):
        assert d in DEFAULT_EXCLUDE_DIRS


def test_iter_files_handles_empty_tree(tmp_path: Path) -> None:
    opts = WatchOptions(root=tmp_path)
    assert list(iter_files(opts)) == []
