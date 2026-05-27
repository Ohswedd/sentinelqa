"""Run-directory retention helper (task 02.05).

`prune_old_runs` removes runs older than ``max_age_days`` AND keeps the
most-recent ``keep_last`` regardless of age. A run with ``keep: true``
in its ``run.json`` is never pruned. The helper is invoked by the CLI
on demand (no auto-pruning in Phase 02).
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine.orchestrator.artifacts import list_runs


def _is_pinned(run_dir: Path) -> bool:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return False
    try:
        data = json.loads(run_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(data.get("keep"))


def prune_old_runs(
    root: Path,
    *,
    keep_last: int,
    max_age_days: int,
    now: datetime | None = None,
) -> list[Path]:
    """Delete eligible runs; return the list of removed directories."""

    if keep_last < 0:
        raise ValueError("keep_last must be >= 0")
    if max_age_days < 0:
        raise ValueError("max_age_days must be >= 0")

    runs = list_runs(root)
    cutoff = (now or datetime.now(UTC)) - timedelta(days=max_age_days)
    removed: list[Path] = []
    survivors = 0
    for run_dir in runs:
        if _is_pinned(run_dir):
            survivors += 1
            continue
        if survivors < keep_last:
            survivors += 1
            continue
        mtime = datetime.fromtimestamp(run_dir.stat().st_mtime, UTC)
        if mtime < cutoff:
            shutil.rmtree(run_dir)
            removed.append(run_dir)
    return removed


__all__ = ["prune_old_runs"]
