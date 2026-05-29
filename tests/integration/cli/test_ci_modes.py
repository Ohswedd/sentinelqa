"""`sentinel ci` mode integration tests (task 17.04)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.orchestrator.registry import default_registry
from typer.testing import CliRunner

from tests.integration.cli.conftest import write_config


def _run(
    runner: CliRunner,
    cli,
    project: Path,
    runs_root: Path,
    *,
    extra: list[str] | None = None,
) -> tuple[Path, list[str]]:
    invoked: list[str] = []
    registry = default_registry()
    registry.clear()

    def factory_for(name: str):
        def _factory(cfg, decision):
            invoked.append(name)
            return

        return _factory

    for module_name in ("functional", "security", "accessibility", "performance", "chaos"):
        registry.register_module(module_name, factory_for(module_name))

    try:
        args = [
            "--config",
            str(project / "sentinel.config.yaml"),
            "ci",
            "--output",
            str(runs_root),
        ]
        if extra:
            args.extend(extra)
        result = runner.invoke(cli, args)
    finally:
        registry.clear()

    assert result.exit_code == 0, result.output
    runs = [p for p in runs_root.iterdir() if p.is_dir() and p.name != "latest"]
    assert runs, "no run directory created"
    return runs[0], invoked


def test_fast_mode_runs_p0_smoke(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    run_dir, invoked = _run(runner, cli, fresh_project, tmp_path / "runs", extra=["--mode", "fast"])
    # fast preset wants functional + security, drops the rest
    assert set(invoked) <= {"functional", "security"}
    assert "functional" in invoked
    ci_meta = json.loads((run_dir / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["mode"] == "fast"
    assert ci_meta["grep"] == "@p0"
    assert ci_meta["schema_version"] == "1"


def test_standard_mode_default_runs_p0_p1(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    run_dir, invoked = _run(runner, cli, fresh_project, tmp_path / "runs")
    # default mode is standard
    assert "functional" in invoked
    assert "accessibility" in invoked
    assert "security" in invoked
    assert "performance" not in invoked  # standard doesn't include perf
    ci_meta = json.loads((run_dir / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["mode"] == "standard"
    assert ci_meta["grep"] == "@p0|@p1"


def test_full_mode_runs_every_module_no_grep(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    run_dir, invoked = _run(runner, cli, fresh_project, tmp_path / "runs", extra=["--mode", "full"])
    # full preset includes functional + accessibility + performance + security
    assert {"functional", "accessibility", "performance", "security"} <= set(invoked)
    ci_meta = json.loads((run_dir / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["mode"] == "full"
    assert ci_meta["grep"] is None


def test_nightly_mode_force_enables_chaos(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    run_dir, invoked = _run(
        runner, cli, fresh_project, tmp_path / "runs", extra=["--mode", "nightly"]
    )
    assert "chaos" in invoked
    ci_meta = json.loads((run_dir / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["extras"] == {"extended_security": True}


def test_release_mode_raises_floor(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    run_dir, _ = _run(runner, cli, fresh_project, tmp_path / "runs", extra=["--mode", "release"])
    ci_meta = json.loads((run_dir / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["mode"] == "release"
    assert ci_meta["policy_overrides"] == {"min_quality_score": 90}


def test_fail_under_wins_over_release_default(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    run_dir, _ = _run(
        runner,
        cli,
        fresh_project,
        tmp_path / "runs",
        extra=["--mode", "release", "--fail-under", "70"],
    )
    ci_meta = json.loads((run_dir / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["fail_under_override"] == 70


def test_invalid_mode_exits_config_error(fresh_project: Path, tmp_path: Path) -> None:
    """Exit code 2 (config error) — verified via ``main()`` so the typed
    ``InvalidCiModeError`` is mapped per :mod:`sentinel_cli.main`."""

    from sentinel_cli.main import main

    write_config(fresh_project)
    code = main(
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "ci",
            "--mode",
            "bogus",
            "--output",
            str(tmp_path / "runs"),
        ]
    )
    assert code == 2


def test_ci_json_output(runner: CliRunner, cli, fresh_project: Path, tmp_path: Path) -> None:
    write_config(fresh_project)
    registry = default_registry()
    registry.clear()
    try:
        result = runner.invoke(
            cli,
            [
                "--config",
                str(fresh_project / "sentinel.config.yaml"),
                "--json",
                "ci",
                "--mode",
                "fast",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "ci"
    assert payload["mode"] == "fast"
    assert payload["grep"] == "@p0"
    assert payload["ci_metadata_path"].endswith("ci.json")


def test_ci_diff_is_persisted_in_metadata(
    runner: CliRunner,
    cli,
    fresh_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--diff is persisted into ci.json. Git is mocked so the test stays
    hermetic and survives shallow CI clones (CLAUDE.md §39)."""

    from engine.ci.diff_aware import select_from_files as _pure

    def fake_git_select(*, diff_range: str, repo_root: Path):
        return _pure(diff_range=diff_range, changed_files=["app/dashboard/page.tsx"])

    monkeypatch.setattr(
        "sentinel_cli.commands.ci_cmd.select_from_git",
        fake_git_select,
    )

    write_config(fresh_project)
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
                "full",
                "--diff",
                "origin/main...HEAD",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()
    assert result.exit_code == 0, result.output
    runs = [p for p in (tmp_path / "runs").iterdir() if p.is_dir() and p.name != "latest"]
    ci_meta = json.loads((runs[0] / "ci.json").read_text(encoding="utf-8"))
    assert ci_meta["diff_range"] == "origin/main...HEAD"


def test_ci_user_grep_is_combined_with_mode_grep(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
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
                "--grep",
                "login",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()
    assert result.exit_code == 0, result.output
    runs = [p for p in (tmp_path / "runs").iterdir() if p.is_dir() and p.name != "latest"]
    ci_meta = json.loads((runs[0] / "ci.json").read_text(encoding="utf-8"))
    # user grep persisted, mode grep stays the preset value
    assert ci_meta["user_grep"] == "login"
    assert ci_meta["grep"] == "@p0|@p1"
