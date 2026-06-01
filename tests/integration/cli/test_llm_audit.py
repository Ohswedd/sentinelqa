"""CLI integration tests for ``sentinel llm-audit``."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def _ensure_module_registered() -> None:
    """Earlier CLI tests (e.g. test_dry_run) clear the process-wide
    registry, leaving the LLM-audit module unregistered. Re-register
    before each test so we don't rely on import-time side effects."""

    from modules.llm_audit import register_with_default_registry

    register_with_default_registry()


def _write_signals(signals_root: Path, payload: dict[str, object]) -> None:
    signals_root.mkdir(parents=True, exist_ok=True)
    (signals_root / "signals.json").write_text(json.dumps(payload), encoding="utf-8")


def _invoke(
    cli_runner: CliRunner,
    project: Path,
    *args: str,
) -> Any:
    app = build_app()
    cwd = os.getcwd()
    os.chdir(project)
    try:
        result = cli_runner.invoke(app, ["llm-audit", *args])
    finally:
        os.chdir(cwd)
    # CliRunner stores stdout/stderr; bubble the typed Result object.
    return result


def test_llm_audit_lists_in_help(cli_runner: CliRunner) -> None:
    app = build_app()
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Typer / rich may wrap; just check the command name appears.
    assert "llm-audit" in result.stdout


def test_llm_audit_no_signals_exits_zero(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    result = _invoke(cli_runner, fresh_project)
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "module_status" in result.stdout


def test_llm_audit_json_mode_emits_single_payload(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    app = build_app()
    cwd = os.getcwd()
    os.chdir(fresh_project)
    try:
        result = cli_runner.invoke(app, ["--json", "llm-audit"])
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "llm-audit"
    assert payload["exit_code"] == 0


def test_llm_audit_invalid_check_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    result = _invoke(cli_runner, fresh_project, "--checks", "not_a_check")
    assert result.exit_code == 2


def test_llm_audit_with_signals_flags_findings(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    signals_root = fresh_project / "signals"
    _write_signals(
        signals_root,
        {
            "rendered_text": [
                {
                    "route_url": "http://localhost:3000/checkout",
                    "text": "Payment step — coming soon",
                    "is_authenticated_flow": True,
                    "priority": "p0",
                }
            ],
        },
    )
    result = _invoke(
        cli_runner,
        fresh_project,
        "--signals",
        str(signals_root),
        "--checks",
        "coming_soon",
    )
    # High-severity finding -> quality gate fails -> exit 1.
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "findings" in result.stdout


def test_llm_audit_missing_config_exits_two(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    project = tmp_path / "noconfig"
    project.mkdir()
    result = _invoke(cli_runner, project)
    assert result.exit_code == 2


def test_llm_audit_empty_checks_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    result = _invoke(cli_runner, fresh_project, "--checks", " , , ")
    assert result.exit_code == 2


def test_llm_audit_url_override_runs(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    result = _invoke(cli_runner, fresh_project, "--url", "http://localhost:3000")
    assert result.exit_code == 0


def test_llm_audit_third_party_hosts_parsed(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    result = _invoke(
        cli_runner,
        fresh_project,
        "--third-party-hosts",
        "ads.example.com, analytics.example.com",
    )
    assert result.exit_code == 0


def test_llm_audit_quiet_mode_silent(
    cli_runner: CliRunner,
    fresh_project: Path,
) -> None:
    write_config(fresh_project)
    app = build_app()
    cwd = os.getcwd()
    os.chdir(fresh_project)
    try:
        result = cli_runner.invoke(app, ["--quiet", "llm-audit"])
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0
    assert result.stdout.strip() == ""
