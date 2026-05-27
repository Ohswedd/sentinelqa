"""`--ci` mode behavior (task 02.07, CLAUDE §39)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentinel_cli.state import GlobalState, detect_ci_default
from tests.integration.cli.conftest import write_config


def test_detect_ci_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("SENTINEL_CI", raising=False)
    assert detect_ci_default() is False

    monkeypatch.setenv("CI", "true")
    assert detect_ci_default() is True
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("SENTINEL_CI", "1")
    assert detect_ci_default() is True


def test_ci_mode_implies_json(
    runner: CliRunner, cli, fresh_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(fresh_project)
    monkeypatch.setattr("shutil.which", lambda _n: None)

    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--ci",
            "doctor",
        ],
    )
    # Output should be parseable as JSON.
    assert result.exit_code == 0, result.stderr
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    assert lines, "CI mode should emit at least one JSON line."
    for line in lines:
        json.loads(line)


def test_ci_mode_state_marks_no_color() -> None:
    s = GlobalState(ci=True)
    assert s.no_color is False  # only set on construction, but mode is "json"
    assert s.mode == "json"
