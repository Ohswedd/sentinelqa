# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the replay-with-change helper."""

from __future__ import annotations

import json
from pathlib import Path

from engine.runs.replay import (
    ReplayRequest,
    apply_patch,
    materialise_tree,
    replay,
    summarise_outcome,
)


def _write_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (root / "node_modules").mkdir(exist_ok=True)
    (root / "node_modules" / "junk.js").write_text("/* big */\n", encoding="utf-8")
    (root / ".sentinel").mkdir(exist_ok=True)
    (root / ".sentinel" / "ignored").write_text("x\n", encoding="utf-8")


def _write_run(path: Path, *, run_id: str, findings: list[dict] | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "passed",
                "quality_score": 90.0,
                "modules_run": ["security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (path / "findings.json").write_text(
        json.dumps({"findings": findings or []}),
        encoding="utf-8",
    )
    (path / "score.json").write_text("{}", encoding="utf-8")


def test_materialise_tree_skips_noisy_dirs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_project(src)
    materialise_tree(src, dst)
    assert (dst / "src" / "main.py").is_file()
    assert not (dst / "node_modules").exists()
    assert not (dst / ".sentinel").exists()


def test_apply_patch_returns_false_for_empty_diff(tmp_path: Path) -> None:
    success, message = apply_patch(tmp_path, "")
    assert success is False
    assert "empty diff" in message


def test_apply_patch_uses_provided_runner(tmp_path: Path) -> None:
    """The runner seam lets tests intercept the ``patch`` invocation."""

    captured: dict[str, object] = {}

    class _R:
        returncode = 0
        stdout = "applied\n"
        stderr = ""

    def fake_runner(args, *, cwd, input, check, capture_output, text, timeout):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["input"] = input
        return _R()

    diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
    success, _ = apply_patch(tmp_path, diff, runner=fake_runner)
    assert success is True
    assert captured["input"] == diff
    args = captured["args"]
    assert isinstance(args, list)
    assert "patch" in args


def test_apply_patch_handles_missing_binary(tmp_path: Path) -> None:
    def fake_runner(*_a, **_k):
        raise FileNotFoundError("no patch")

    success, message = apply_patch(tmp_path, "diff", runner=fake_runner)
    assert success is False
    assert "PATH" in message


def test_apply_patch_returns_stderr_on_failure(tmp_path: Path) -> None:
    class _R:
        returncode = 1
        stdout = ""
        stderr = "hunk failed at line 3"

    def fake_runner(*_a, **_k):
        return _R()

    success, message = apply_patch(tmp_path, "diff", runner=fake_runner)
    assert success is False
    assert "hunk failed" in message


def test_replay_returns_no_runner_when_runner_omitted(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write_project(src)
    before_dir = tmp_path / "before"
    _write_run(before_dir, run_id="RUN-BEFOREAAAAA")

    request = ReplayRequest(
        source_run_dir=before_dir,
        unified_diff="diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n",
        project_root=src,
    )

    class _R:
        returncode = 0
        stdout = ""
        stderr = ""

    outcome = replay(
        request,
        patch_runner=lambda *_a, **_k: _R(),
    )
    assert outcome.success is False
    assert "no runner" in outcome.rationale


def test_replay_returns_patch_failed_outcome_when_patch_does_not_apply(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write_project(src)
    before_dir = tmp_path / "before"
    _write_run(before_dir, run_id="RUN-BEFOREAAAAA")

    request = ReplayRequest(
        source_run_dir=before_dir,
        unified_diff="diff --git a/x b/x\n--- a/x\n+++ b/x\n",
        project_root=src,
    )

    class _R:
        returncode = 1
        stdout = ""
        stderr = "malformed patch"

    outcome = replay(
        request,
        patch_runner=lambda *_a, **_k: _R(),
    )
    assert outcome.success is False
    assert "patch-failed" in outcome.safety_violations


def test_replay_happy_path_calls_runner_and_diffs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write_project(src)
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_run(
        before_dir,
        run_id="RUN-BEFOREAAAAA",
        findings=[
            {
                "id": "FND-XAAAAAAAAAAA",
                "module": "security",
                "category": "headers",
                "severity": "high",
                "title": "CSP missing",
            }
        ],
    )
    _write_run(after_dir, run_id="RUN-AFTERRAAAAA", findings=[])  # all resolved

    request = ReplayRequest(
        source_run_dir=before_dir,
        unified_diff="diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n",
        project_root=src,
    )

    class _PatchR:
        returncode = 0
        stdout = "ok"
        stderr = ""

    captured: dict[str, object] = {}

    def stub_runner(patched_root: Path, req: ReplayRequest) -> tuple[Path, str]:
        captured["patched_root"] = patched_root
        captured["test_ids"] = req.test_ids
        return after_dir, "runner ran"

    outcome = replay(
        request,
        runner=stub_runner,
        patch_runner=lambda *_a, **_k: _PatchR(),
    )
    assert outcome.success is True
    assert outcome.comparison is not None
    assert len(outcome.comparison.resolved) == 1
    assert outcome.new_run_id == "RUN-AFTERRAAAAA"
    assert captured["patched_root"] is not None


def test_replay_catches_runner_exception(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write_project(src)
    before_dir = tmp_path / "before"
    _write_run(before_dir, run_id="RUN-BEFOREAAAAA")

    request = ReplayRequest(
        source_run_dir=before_dir,
        unified_diff="diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n",
        project_root=src,
    )

    class _R:
        returncode = 0
        stdout = ""
        stderr = ""

    def boom(*_a, **_k):
        raise RuntimeError("lifecycle exploded")

    outcome = replay(
        request,
        runner=boom,
        patch_runner=lambda *_a, **_k: _R(),
    )
    assert outcome.success is False
    assert "lifecycle exploded" in outcome.rationale


def test_summarise_outcome_serialises_comparison() -> None:
    from engine.runs.compare import RunComparison
    from engine.runs.replay import ReplayOutcome

    comparison = RunComparison(before_run_id="r1", after_run_id="r2", score_delta=2.0)
    outcome = ReplayOutcome(
        success=True,
        comparison=comparison,
        new_run_id="r2",
        rationale="ok",
    )
    payload = summarise_outcome(outcome)
    assert payload["success"] is True
    assert payload["comparison"]["score_delta"] == 2.0
