# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""End-to-end ``sentinel audit`` tests for v1.2.0 test-economics flags."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from tests.integration.cli.conftest import write_config


def _init_git_repo(root: Path) -> None:
    """Create a minimal git repo so ``--changed-only`` has something to diff."""

    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _stage_commit(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_changed_only_skips_audit_when_no_audit_relevant_changes(
    runner: CliRunner, cli, tmp_path: Path, monkeypatch
) -> None:
    """A docs-only commit must trigger a no-op exit."""

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    _init_git_repo(project)
    write_config(project)
    (project / "src").mkdir()
    (project / "src" / "main.ts").write_text("export const x = 1;\n", encoding="utf-8")
    _stage_commit(project, "init")

    # Modify only README.
    (project / "README.md").write_text("# project\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "--json",
            "audit",
            "--changed-only",
            "--diff-base",
            "HEAD",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "audit"
    assert payload["status"] == "no-op"


def test_changed_only_runs_audit_when_src_changes(
    runner: CliRunner, cli, tmp_path: Path, monkeypatch
) -> None:
    """Modifying a .ts source must run the impacted modules."""

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    _init_git_repo(project)
    write_config(project)
    (project / "src").mkdir()
    (project / "src" / "main.ts").write_text("export const x = 1;\n", encoding="utf-8")
    _stage_commit(project, "init")

    # Drift the source file.
    (project / "src" / "main.ts").write_text("export const x = 2;\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "--json",
            "audit",
            "--changed-only",
            "--diff-base",
            "HEAD",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    # Either a normal audit ran (run_id present) or the JSON status field is "passed".
    assert "run_id" in payload
    assert payload["status"] != "no-op"


def test_changed_only_fails_when_not_a_git_repo(
    runner: CliRunner, cli, tmp_path: Path, monkeypatch
) -> None:
    """Without a git repo, ``--changed-only`` must exit with a clear error."""

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    write_config(project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "audit",
            "--changed-only",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 2, result.output


def test_since_latest_short_circuits_when_source_unchanged(
    runner: CliRunner, cli, tmp_path: Path, monkeypatch
) -> None:
    """A second audit with --since latest must skip when nothing changed."""

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    write_config(project)
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")

    artifacts = tmp_path / "runs"

    # Run once to populate ``latest/``.
    first = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "audit",
            "--output",
            str(artifacts),
        ],
    )
    assert first.exit_code == 0, first.output

    # Second invocation with --since latest must short-circuit.
    second = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "--json",
            "audit",
            "--since",
            "latest",
            "--output",
            str(artifacts),
        ],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.stdout.strip())
    assert payload["status"] == "unchanged"


def test_since_runs_audit_when_source_drifted(
    runner: CliRunner, cli, tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    write_config(project)
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    artifacts = tmp_path / "runs"
    runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "audit",
            "--output",
            str(artifacts),
        ],
    )

    # Drift.
    (project / "src" / "main.py").write_text("x = 2\n", encoding="utf-8")

    second = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "--json",
            "audit",
            "--since",
            "latest",
            "--output",
            str(artifacts),
        ],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.stdout.strip())
    assert payload.get("status") != "unchanged"
    assert "run_id" in payload


def test_parallel_modules_flag_runs_to_completion(
    runner: CliRunner, cli, tmp_path: Path, monkeypatch
) -> None:
    """``--parallel-modules`` is a CLI surface only; lifecycle behaviour is covered upstream."""

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    write_config(project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "audit",
            "--parallel-modules",
            "4",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output


def test_parallel_modules_rejects_out_of_range(runner: CliRunner, cli, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    write_config(project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "audit",
            "--parallel-modules",
            "99",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 2, result.output
