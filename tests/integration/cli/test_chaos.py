"""CLI integration tests for ``sentinel chaos``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


@pytest.fixture(autouse=True)
def _ensure_chaos_registered() -> None:
    """Some earlier tests clear the orchestrator registry. Re-register chaos.

    `register_with_default_registry()` is idempotent (CLAUDE §9 module
    contract), so calling it per-test costs nothing and keeps the
    chaos CLI tests independent of suite ordering.
    """

    from modules.chaos import register_with_default_registry

    register_with_default_registry()


@pytest.fixture
def cli_app():
    return build_app()


def _write_events(project_root: Path, lines: list[dict]) -> Path:
    chaos_dir = project_root / "chaos"
    chaos_dir.mkdir(parents=True, exist_ok=True)
    path = chaos_dir / "events.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    return path


def test_chaos_clean_returns_exit_zero(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["--no-ci", "chaos"])
    # No events file → every category skipped → status passed → exit 0.
    assert result.exit_code == 0, result.stderr


def test_chaos_high_finding_returns_quality_gate_failed(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    events_path = _write_events(
        tmp_path,
        [
            {
                "scenario_id": "network.api_500",
                "category": "network",
                "flow": "checkout",
                "observation": "no_error_state",
                "route": "/api/checkout",
            }
        ],
    )
    result = runner.invoke(
        cli_app,
        ["--no-ci", "chaos", "--events", str(events_path)],
    )
    assert result.exit_code == 1, result.stderr


def test_chaos_json_mode_emits_machine_readable(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["--json", "chaos"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == "chaos"
    assert "run_id" in payload
    assert "exit_code" in payload


def test_chaos_unknown_category_returns_config_error(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["chaos", "--categories", "bogus"])
    assert result.exit_code == 2


def test_chaos_url_override_changes_target(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:9000")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["--no-ci", "chaos", "--url", "http://127.0.0.1:7000"])
    assert result.exit_code == 0


def test_chaos_unsafe_target_returns_exit_4(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:3000")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["--no-ci", "chaos", "--url", "http://attacker.example.com"])
    assert result.exit_code == 4, result.stderr
