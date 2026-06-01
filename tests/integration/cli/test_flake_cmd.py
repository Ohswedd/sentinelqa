# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""End-to-end CLI tests for ``sentinel flake``."""

from __future__ import annotations

import json
from pathlib import Path

from engine.persistence import FlakeDb, Outcome
from typer.testing import CliRunner

from sentinel_cli.app import build_app


def _seed_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with FlakeDb.open(path) as db:
        for i in range(10):
            run_id = f"RUN-XXXX{i:04d}AAAA"
            db.record_run(run_id, started_at=f"2026-06-01T00:{i:02d}:00+00:00", status="passed")
            db.record_outcome(
                Outcome(
                    run_id=run_id,
                    module="functional",
                    test_id="login-flow",
                    outcome="failed" if i % 2 == 0 else "passed",
                )
            )


def test_flake_stats_prints_runs_and_outcomes(tmp_path: Path) -> None:
    db_path = tmp_path / "flake.db"
    _seed_db(db_path)
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["flake", "stats", "--db", str(db_path)])
    assert result.exit_code == 0, result.output
    assert "runs    : 10" in result.stdout
    assert "outcomes: 10" in result.stdout


def test_flake_list_returns_seeded_test(tmp_path: Path) -> None:
    db_path = tmp_path / "flake.db"
    _seed_db(db_path)
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["--json", "flake", "list", "--db", str(db_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["command"] == "flake.list"
    assert any(r["test_id"] == "login-flow" for r in payload["results"])
    assert payload["results"][0]["rate"] == 0.5


def test_flake_list_without_db_returns_empty(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["--json", "flake", "list", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"] == []


def test_flake_stats_without_db_returns_zero(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["--json", "flake", "stats", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["runs"] == 0
    assert payload["outcomes"] == 0


def test_flake_help_lists_subcommands() -> None:
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["flake", "--help"], terminal_width=200)
    assert result.exit_code == 0
    assert "list" in result.output
    assert "stats" in result.output


def test_flake_list_human_output_lists_seeded_test(tmp_path: Path) -> None:
    """The default (human) mode prints the table header + each row."""

    db_path = tmp_path / "flake.db"
    _seed_db(db_path)
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["flake", "list", "--db", str(db_path)])
    assert result.exit_code == 0, result.output
    assert "MODULE" in result.stdout
    assert "functional" in result.stdout
    assert "login-flow" in result.stdout
    assert "50%" in result.stdout


def test_flake_list_quiet_mode_is_tab_separated(tmp_path: Path) -> None:
    db_path = tmp_path / "flake.db"
    _seed_db(db_path)
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["--quiet", "flake", "list", "--db", str(db_path)])
    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert any(line.startswith("functional\tlogin-flow\t5/10") for line in lines), result.stdout


def test_flake_stats_human_mode_prints_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "flake.db"
    _seed_db(db_path)
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["flake", "stats", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "runs    : 10" in result.stdout


def test_flake_list_missing_db_human_mode_explains(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["flake", "list", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 0
    assert "No flake DB found" in result.stdout


def test_flake_list_empty_db_human_mode_shows_no_pairs(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    # Touch the DB so the file-exists check passes but no rows are recorded.
    from engine.persistence import FlakeDb

    FlakeDb.open(db_path).close()
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(app, ["flake", "list", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "No (module, test_id) pairs" in result.stdout


def test_flake_list_respects_min_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "flake.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with FlakeDb.open(db_path) as db:
        # Only 2 runs of t1 with 100% rate — below the default floor of 3.
        for i in range(2):
            run_id = f"RUN-XXXX{i:04d}BBBB"
            db.record_run(run_id, f"2026-06-01T00:{i:02d}:00+00:00", "passed")
            db.record_outcome(Outcome(run_id=run_id, module="m", test_id="t1", outcome="failed"))
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(
        app, ["--json", "flake", "list", "--db", str(db_path), "--min-runs", "3"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"] == []
