"""`--json` mode emits ONLY JSON to stdout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentinel_cli.json_mode import json_stdout
from tests.integration.cli.conftest import write_config


def test_init_json_stdout_is_pure_json(runner: CliRunner, cli, fresh_project: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--json",
            "init",
            "--path",
            str(fresh_project),
        ],
    )
    assert result.exit_code == 0, result.stderr
    for line in result.stdout.strip().splitlines():
        if line == "":
            continue
        json.loads(line)


def test_doctor_json_stdout_is_pure_json(
    runner: CliRunner, cli, fresh_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(fresh_project)
    # Skip subprocess + httpx calls.
    monkeypatch.setattr("shutil.which", lambda _name: None)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--json",
            "doctor",
        ],
    )
    # Doctor returns 0 even with warns, as long as no fails.
    for line in result.stdout.strip().splitlines():
        if line == "":
            continue
        json.loads(line)


def test_json_stdout_guard_rejects_non_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The optional environment-driven guard catches a stray plain-text
    write to stdout while json_stdout is active."""

    import sys

    monkeypatch.setenv("SENTINELQA_ASSERT_JSON_STDOUT", "1")

    with pytest.raises(AssertionError), json_stdout() as out:
        out.emit({"hello": "world"})
        sys.stdout.write("this is not JSON\n")
