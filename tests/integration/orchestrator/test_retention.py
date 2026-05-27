"""prune_old_runs behavior."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.retention import prune_old_runs


def _set_mtime(path: Path, mtime: float) -> None:
    os.utime(path, (mtime, mtime))


def test_keeps_last_n(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    for i in range(5):
        art = ArtifactDirectory.create(root, f"RUN-AA{i:02d}AAAAAAAA")
        art.write_json("run.json", {"id": f"run-{i}"})
        _set_mtime(art.root, time.time() - (i + 1) * 86400)

    removed = prune_old_runs(root, keep_last=3, max_age_days=0)
    assert len(removed) == 2
    survivors = {p.name for p in root.iterdir() if p.is_dir()}
    assert len(survivors) == 3


def test_pinned_runs_kept(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    pinned = ArtifactDirectory.create(root, "RUN-PINNEDDDDDDD")
    pinned.write_json("run.json", {"id": "pinned", "keep": True})
    _set_mtime(pinned.root, time.time() - 365 * 86400)

    for i in range(3):
        art = ArtifactDirectory.create(root, f"RUN-AA{i:02d}AAAAAAAA")
        art.write_json("run.json", {"id": f"run-{i}"})
        _set_mtime(art.root, time.time() - (i + 1) * 86400)

    removed = prune_old_runs(root, keep_last=0, max_age_days=0)
    survivors = {p.name for p in root.iterdir() if p.is_dir()}
    assert "RUN-PINNEDDDDDDD" in survivors
    assert pinned.root not in removed


def test_no_runs_no_error(tmp_path: Path) -> None:
    removed = prune_old_runs(tmp_path / "missing", keep_last=5, max_age_days=30)
    assert removed == []


def test_rejects_negative_args(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        prune_old_runs(tmp_path, keep_last=-1, max_age_days=30)
    with pytest.raises(ValueError):
        prune_old_runs(tmp_path, keep_last=5, max_age_days=-1)
