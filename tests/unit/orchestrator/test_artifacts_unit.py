"""Unit-level helpers around ArtifactDirectory."""

from __future__ import annotations

import json
from pathlib import Path

from engine.orchestrator.artifacts import ArtifactDirectory, list_runs


def test_append_line_creates_and_appends(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    art.append_line("audit.log", '{"event":"first"}')
    art.append_line("audit.log", '{"event":"second"}')
    body = (art.root / "audit.log").read_text(encoding="utf-8")
    assert body.count("\n") == 2
    assert "first" in body
    assert "second" in body


def test_write_yaml_redacts(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    art.write_yaml("config.yaml", {"api_key": "super-secret-1234"})
    body = (art.root / "config.yaml").read_text(encoding="utf-8")
    assert "super-secret-1234" not in body


def test_write_text_atomic(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    art.write_text("notes.txt", "hello world")
    assert (art.root / "notes.txt").read_text(encoding="utf-8") == "hello world"


def test_list_runs_skips_latest_symlink(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    ArtifactDirectory.create(runs, "RUN-XYZ12345ABCD")
    # Manually create a `latest` entry (file form for cross-OS) — list_runs
    # must filter it.
    (runs / "latest").write_text("RUN-XYZ12345ABCD", encoding="utf-8")
    found = list_runs(runs)
    assert all(p.name != "latest" for p in found)


def test_jsonable_path_coercion(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-AAAABBBBCCCC")
    art.write_json("paths.json", {"where": Path("/etc/hosts")})
    data = json.loads((art.root / "paths.json").read_text(encoding="utf-8"))
    assert data["where"] == "/etc/hosts"
