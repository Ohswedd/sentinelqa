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
