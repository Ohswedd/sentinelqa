"""`sentinel audit` flag handling."""

from __future__ import annotations

import json
from pathlib import Path

from engine.orchestrator.registry import default_registry
from typer.testing import CliRunner

from tests.integration.cli.conftest import write_config


def test_audit_url_override(runner: CliRunner, cli, fresh_project: Path, tmp_path: Path) -> None:
    write_config(fresh_project, base_url="http://localhost:3000")
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "audit",
            "--url",
            "http://localhost:4000",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output
    # Find run.json under tmp_path/runs
    run_dirs = [p for p in (tmp_path / "runs").iterdir() if p.is_dir() and p.name != "latest"]
    assert run_dirs
    payload = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert "4000" in payload["target"]["base_url"]


def test_audit_modules_filter(runner: CliRunner, cli, fresh_project: Path, tmp_path: Path) -> None:
    write_config(fresh_project)
    registry = default_registry()
    registry.clear()
    invoked: list[str] = []

    def fn_factory(cfg, decision):
        invoked.append("functional")
        return

    registry.register_module("functional", fn_factory)
    try:
        result = runner.invoke(
            cli,
            [
                "--config",
                str(fresh_project / "sentinel.config.yaml"),
                "audit",
                "--modules",
                "functional",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()
    assert result.exit_code == 0, result.output
    assert invoked == ["functional"]


def test_audit_json_output(runner: CliRunner, cli, fresh_project: Path, tmp_path: Path) -> None:
    write_config(fresh_project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--json",
            "audit",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "audit"
    assert "run_id" in payload


def test_audit_watch_refuses_in_ci_mode(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    """``--watch`` is a local-dev affordance and must refuse to start in CI mode."""

    write_config(fresh_project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--ci",
            "audit",
            "--watch",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    # EXIT_CONFIG_ERROR = 2
    assert result.exit_code == 2, result.output


def test_audit_watch_runs_initial_audit_and_exits_via_keyboard_interrupt(
    monkeypatch,
    runner: CliRunner,
    cli,
    fresh_project: Path,
    tmp_path: Path,
) -> None:
    """``--watch`` runs the initial audit through the lifecycle then loops; Ctrl+C clean-exits."""

    write_config(fresh_project)

    from sentinel_cli.commands import audit_cmd as mod

    captured: dict[str, object] = {}

    def fake_watch_loop(opts, run_audit, *, out=None, **_kwargs):
        captured["root"] = opts.root
        run_audit()  # exercise the inner closure (runs lifecycle + status print)
        raise KeyboardInterrupt

    monkeypatch.setattr(mod, "watch_loop", fake_watch_loop)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "audit",
            "--watch",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "root" in captured


def test_audit_fail_under_override_threads_through_config(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    """``--fail-under`` rewrites ``policy.min_quality_score`` on the loaded config."""

    write_config(fresh_project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--json",
            "audit",
            "--fail-under",
            "0",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "audit"
