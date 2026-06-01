"""Additional CLI integration tests for ``sentinel generate``.

Cover the ``--from-plan`` / ``--from-discovery`` branches and the
audit failure surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config
from tests.integration.discovery.conftest import discovery_server  # noqa: F401


def _stage_discovery_and_plan(
    runner: CliRunner,
    project: Path,
    base_url: str,
) -> Path:
    cli = build_app()
    discover = runner.invoke(
        cli,
        [
            "discover",
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
    assert discover.exit_code == 0, discover.stdout + discover.stderr
    runs_root = project / ".sentinel" / "runs"
    discover_run = next(iter(runs_root.iterdir()))

    plan_run = runner.invoke(
        cli,
        ["plan", "--from-discovery", str(discover_run), "--no-llm"],
    )
    assert plan_run.exit_code == 0, plan_run.stdout + plan_run.stderr
    # New plan run dir → find the one that contains plan.json.
    plan_dirs = [d for d in runs_root.iterdir() if (d / "plan.json").exists()]
    assert plan_dirs, list(runs_root.iterdir())
    return discover_run


def test_generate_from_plan_path(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    discover_run = _stage_discovery_and_plan(runner, fresh_project, base_url)
    plan_json = (
        next(
            d
            for d in (fresh_project / ".sentinel" / "runs").iterdir()
            if (d / "plan.json").exists()
        )
        / "plan.json"
    )

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--from-plan",
            str(plan_json),
            "--from-discovery",
            str(discover_run),
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (fresh_project / "tests" / "sentinel" / "sentinel.generated.plan.md").exists()


def test_generate_from_plan_without_from_discovery_rejected(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    _stage_discovery_and_plan(runner, fresh_project, base_url)
    plan_json = (
        next(
            d
            for d in (fresh_project / ".sentinel" / "runs").iterdir()
            if (d / "plan.json").exists()
        )
        / "plan.json"
    )

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--from-plan",
            str(plan_json),
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
            "--no-audit",
        ],
    )
    # typer wraps BadParameter in a rich error box; the exact message
    # is truncated in CI output, so we just assert the non-zero exit
    # code (BadParameter maps to typer's usage error → 2).
    assert result.exit_code != 0


def test_generate_quiet_mode_silent_on_success(
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
            "--quiet",
            "generate",
            "--url",
            base_url,
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_generate_from_discovery_uses_existing_artifacts(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    discover_run = _stage_discovery_and_plan(runner, fresh_project, base_url)
    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "--json",
            "generate",
            "--from-discovery",
            str(discover_run),
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "generate"


def test_generate_from_discovery_missing_dir_errors(
    runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project, base_url="http://localhost:3000")

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--from-discovery",
            str(fresh_project / "nope"),
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
            "--no-audit",
        ],
    )
    # BadParameter from typer → non-zero exit. The exact error message
    # is wrapped in a rich error box and ANSI-colored in CI, so we
    # only assert exit code here.
    assert result.exit_code != 0
