"""Global option propagation (task 02.01 + 02.06 + 02.07)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sentinel_cli.state import GlobalState


def test_state_resolves_modes() -> None:
    s = GlobalState()
    assert s.mode == "human"
    s = GlobalState(quiet=True)
    assert s.mode == "quiet"
    s = GlobalState(json=True)
    assert s.mode == "json"
    s = GlobalState(ci=True)
    assert s.mode == "json"  # CI implies JSON


def test_json_flag_propagates_to_init(
    runner: CliRunner,
    cli,
    fresh_project: Path,
) -> None:
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
    # JSON mode emits exactly one JSON object to stdout.
    import json

    line = result.stdout.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["command"] == "init"


def test_quiet_suppresses_output(runner: CliRunner, cli, fresh_project: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--quiet",
            "init",
            "--path",
            str(fresh_project),
        ],
    )
    assert result.exit_code == 0, result.stderr
    # Nothing on stdout in quiet mode for a successful init.
    assert result.stdout.strip() == ""
