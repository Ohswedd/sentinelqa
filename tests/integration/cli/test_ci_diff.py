"""CLI integration tests for ``sentinel ci --diff`` (task 17.05)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.orchestrator.registry import default_registry
from typer.testing import CliRunner

from tests.integration.cli.conftest import write_config


def test_cli_diff_path_persists_selection(
    runner: CliRunner,
    cli,
    fresh_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(fresh_project)

    def fake_git_select(*, diff_range: str, repo_root: Path):
        from engine.ci.diff_aware import select_from_files as _pure

        return _pure(diff_range=diff_range, changed_files=["app/dashboard/page.tsx"])

    monkeypatch.setattr(
        "sentinel_cli.commands.ci_cmd.select_from_git",
        fake_git_select,
    )

    registry = default_registry()
    registry.clear()
    try:
        result = runner.invoke(
            cli,
            [
                "--config",
                str(fresh_project / "sentinel.config.yaml"),
                "ci",
                "--mode",
                "standard",
                "--diff",
                "origin/main...HEAD",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()

    assert result.exit_code == 0, result.output
    run_dirs = [p for p in (tmp_path / "runs").iterdir() if p.is_dir() and p.name != "latest"]
    payload = json.loads((run_dirs[0] / "ci.json").read_text(encoding="utf-8"))
    selection = payload["diff_selection"]
    assert selection is not None
    assert selection["impacted_routes"] == ["/dashboard"]
    assert selection["fallback_to_full"] is False


def test_cli_diff_broad_change_triggers_full_fallback(
    runner: CliRunner,
    cli,
    fresh_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(fresh_project)

    def fake_git_select(*, diff_range: str, repo_root: Path):
        from engine.ci.diff_aware import select_from_files as _pure

        return _pure(diff_range=diff_range, changed_files=["pnpm-lock.yaml"])

    monkeypatch.setattr(
        "sentinel_cli.commands.ci_cmd.select_from_git",
        fake_git_select,
    )

    registry = default_registry()
    registry.clear()
    try:
        result = runner.invoke(
            cli,
            [
                "--config",
                str(fresh_project / "sentinel.config.yaml"),
                "ci",
                "--mode",
                "fast",
                "--diff",
                "origin/main...HEAD",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()

    assert result.exit_code == 0, result.output
    run_dirs = [p for p in (tmp_path / "runs").iterdir() if p.is_dir() and p.name != "latest"]
    payload = json.loads((run_dirs[0] / "ci.json").read_text(encoding="utf-8"))
    selection = payload["diff_selection"]
    assert selection["fallback_to_full"] is True


def test_cli_diff_missing_git_returns_dependency_error(
    fresh_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When git is missing, ``--diff`` surfaces exit code 5 (dependency)."""

    from sentinel_cli.main import main

    write_config(fresh_project)

    def boom(*, diff_range: str, repo_root: Path):
        raise FileNotFoundError("git not on PATH")

    monkeypatch.setattr(
        "sentinel_cli.commands.ci_cmd.select_from_git",
        boom,
    )

    code = main(
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "ci",
            "--diff",
            "origin/main...HEAD",
            "--output",
            str(tmp_path / "runs"),
        ]
    )
    assert code == 5
