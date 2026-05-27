"""`.sentinel/runs/latest` points at the newest run."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.symlinks import update_latest_pointer


def test_latest_points_at_run(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    art = ArtifactDirectory.create(root, "RUN-ABCDEFGHJKMN")
    art.write_json("run.json", {"id": "first"})

    latest = update_latest_pointer(root, art.root)
    assert latest.exists() or latest.is_symlink()
    if os.name != "nt":
        target = os.readlink(latest)
        assert target == "RUN-ABCDEFGHJKMN"


def test_latest_replaces_previous(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    a = ArtifactDirectory.create(root, "RUN-AAAAAAAAAAAA")
    a.write_json("run.json", {"id": "a"})
    update_latest_pointer(root, a.root)

    b = ArtifactDirectory.create(root, "RUN-BBBBBBBBBBBB")
    b.write_json("run.json", {"id": "b"})
    update_latest_pointer(root, b.root)

    if os.name != "nt":
        target = os.readlink(root / "latest")
        assert target == "RUN-BBBBBBBBBBBB"


def test_refuses_to_overwrite_real_directory(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    (root / "latest").mkdir()  # real directory, not a symlink

    with pytest.raises(OSError):
        update_latest_pointer(root, root / "RUN-XYZ")
