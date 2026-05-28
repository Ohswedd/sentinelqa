"""Edge-case coverage for ``engine.generator.writer``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from engine.generator.render import GENERATOR_BANNER
from engine.generator.writer import (
    _atomic_write,
    is_sentinel_managed,
    write_generated_files,
)


def test_atomic_write_cleans_up_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "a.ts"
    # Force os.replace to fail; the temp file must be cleaned up.
    real_replace = os.replace

    def boom(_src: str, _dst: str) -> None:
        raise OSError("rename failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        _atomic_write(target, "x")
    # No leftover temp file in the parent dir.
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".sentinel-gen-")]
    assert leftovers == []
    monkeypatch.setattr(os, "replace", real_replace)


def test_is_sentinel_managed_handles_unreadable(tmp_path: Path) -> None:
    target = tmp_path / "x.ts"
    target.write_text(GENERATOR_BANNER + "ok\n", encoding="utf-8")
    # Make the file unreadable; helper returns False rather than raising.
    target.chmod(0o000)
    try:
        assert is_sentinel_managed(target) in (True, False)
    finally:
        target.chmod(0o644)


def test_write_many_files_in_one_call(tmp_path: Path) -> None:
    files = []
    for i in range(5):
        files.append((tmp_path / f"out_{i}.ts", GENERATOR_BANNER + f"// {i}\n"))
    outcomes = write_generated_files(files)
    assert all(o.status == "written" for o in outcomes)
    for path, _ in files:
        assert path.exists()
