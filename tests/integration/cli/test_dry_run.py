"""`--dry-run` behavior (task 02.07)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.orchestrator.registry import default_registry
from typer.testing import CliRunner

from tests.integration.cli.conftest import write_config


def test_audit_dry_run_does_not_invoke_modules(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
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
                "--dry-run",
                "audit",
                "--output",
                str(tmp_path / "runs"),
            ],
        )
    finally:
        registry.clear()
    assert result.exit_code == 0, result.output
    assert invoked == []


def test_audit_dry_run_writes_plan(
    runner: CliRunner, cli, fresh_project: Path, tmp_path: Path
) -> None:
    write_config(fresh_project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--dry-run",
            "audit",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 0, result.output

    # Find the run directory.
    run_dirs = [p for p in (tmp_path / "runs").iterdir() if p.is_dir() and p.name != "latest"]
    assert len(run_dirs) == 1
    plan = json.loads((run_dirs[0] / "plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run"] is True
    run_payload = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "dry_run"
