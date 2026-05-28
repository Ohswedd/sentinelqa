"""CLI integration tests for ``sentinel plan`` (task 06.05)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config

# Re-use the discovery HTTP server fixture so the planner has a real-ish target.
from tests.integration.discovery.conftest import (  # noqa: F401
    discovery_base_url,
    discovery_server,
)


def test_plan_writes_plan_json_and_md(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "plan",
            "--url",
            base_url,
            "--max-depth",
            "1",
            "--max-pages",
            "10",
            "--rate-limit",
            "50",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr

    runs_root = fresh_project / ".sentinel" / "runs"
    assert runs_root.exists()
    run_dirs = list(runs_root.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "plan.md").exists()
    payload = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert payload["plan"]["id"].startswith("PLN-")


def test_plan_from_existing_discovery(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    cli = build_app()
    # First, run discover to produce a run directory we can replay.
    discover_result = runner.invoke(
        cli,
        ["discover", "--url", base_url, "--max-depth", "1", "--max-pages", "5"],
    )
    assert discover_result.exit_code == 0
    runs_root = fresh_project / ".sentinel" / "runs"
    discovery_run_dir = next(runs_root.iterdir())

    # Now run plan with --from-discovery.
    plan_result = runner.invoke(
        cli,
        [
            "plan",
            "--from-discovery",
            str(discovery_run_dir),
        ],
    )
    assert plan_result.exit_code == 0, plan_result.stdout + plan_result.stderr
    # A new run dir is created for the plan output.
    plan_runs = [d for d in runs_root.iterdir() if d != discovery_run_dir]
    assert plan_runs
    plan_run_dir = plan_runs[0]
    assert (plan_run_dir / "plan.json").exists()


def test_plan_json_mode_emits_machine_readable_output(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "--json",
            "plan",
            "--url",
            base_url,
            "--max-pages",
            "5",
            "--max-depth",
            "1",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == "plan"
    assert payload["plan_id"].startswith("PLN-")
    assert "coverage_estimate" in payload
    assert "llm_flows_added" in payload


def test_plan_no_llm_flag_disables_llm(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with no key configured, --no-llm must be respected and succeed."""

    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    cli = build_app()
    result = runner.invoke(
        cli,
        ["plan", "--url", base_url, "--no-llm", "--max-pages", "5", "--max-depth", "1"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr


def test_plan_rejects_missing_discovery_input(
    runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)

    cli = build_app()
    result = runner.invoke(
        cli,
        ["plan", "--from-discovery", str(tmp_path / "nope")],
    )
    assert result.exit_code != 0
