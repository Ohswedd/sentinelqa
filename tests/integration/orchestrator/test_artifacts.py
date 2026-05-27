"""ArtifactDirectory atomic writes + redaction."""

from __future__ import annotations

import json
from pathlib import Path

from engine.orchestrator.artifacts import ArtifactDirectory, list_runs


def test_create_makes_run_dir(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    assert art.root.is_dir()
    assert art.root.name == "RUN-ABCDEFGHJKMN"


def test_write_json_redacts(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    art.write_json("payload.json", {"username": "alice", "password": "shhh-1234"})
    data = json.loads((art.root / "payload.json").read_text(encoding="utf-8"))
    assert data["username"] == "alice"
    # Redaction layer masks the value of "password".
    assert "shhh-1234" not in (art.root / "payload.json").read_text(encoding="utf-8")
    assert data["password"].startswith("[REDACTED")


def test_write_json_is_atomic_no_partial_files(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    art.write_json("ok.json", {"hello": "world"})
    leftovers = list((art.root).glob("*.tmp"))
    assert leftovers == []


def test_subdir_creates_and_returns(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    sub = art.subdir("traces")
    assert sub.is_dir()
    assert sub.name == "traces"


def test_no_placeholder_files_created(tmp_path: Path) -> None:
    art = ArtifactDirectory.create(tmp_path / "runs", "RUN-ABCDEFGHJKMN")
    # The constructor must NOT eagerly create empty files.
    assert not (art.root / "findings.json").exists()
    assert not (art.root / "score.json").exists()
    assert not (art.root / "report.html").exists()


def test_list_runs_newest_first(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    a = ArtifactDirectory.create(root, "RUN-AAAAAAAAAAAA")
    b = ArtifactDirectory.create(root, "RUN-BBBBBBBBBBBB")
    a.write_json("run.json", {"id": "a"})
    b.write_json("run.json", {"id": "b"})
    ordered = list_runs(root)
    assert [p.name for p in ordered] == ["RUN-BBBBBBBBBBBB", "RUN-AAAAAAAAAAAA"]
