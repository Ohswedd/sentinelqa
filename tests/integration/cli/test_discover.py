"""CLI integration tests for ``sentinel discover``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config

# Re-use the discovery server fixture from the discovery integration package.
from tests.integration.discovery.conftest import discovery_base_url, discovery_server  # noqa: F401


def test_discover_writes_artifacts(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811 — pytest fixture reuse
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
    assert result.exit_code == 0, result.stdout + result.stderr
    # Find the run dir.
    runs_root = fresh_project / ".sentinel" / "runs"
    assert runs_root.exists()
    run_dirs = list(runs_root.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    for name in ("discovery.json", "forms.json", "api.json", "auth.json", "risk.json"):
        assert (run_dir / name).exists()
    assert (run_dir / "discovery.report.md").exists()
    discovery_payload = json.loads((run_dir / "discovery.json").read_text())
    assert discovery_payload["schema_version"]
    assert discovery_payload["graph"]["routes"]


def test_discover_json_mode_emits_one_object(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811 — pytest fixture reuse
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
            "discover",
            "--url",
            base_url,
            "--max-depth",
            "0",
            "--max-pages",
            "1",
            "--rate-limit",
            "50",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    # Each line in stdout should parse as JSON; the command emits one summary line.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["command"] == "discover"
    assert payload["run_id"].startswith("RUN-")
    assert payload["routes"] >= 1


def test_discover_blocks_unsafe_target(
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project, base_url="http://localhost:3000")
    # Public host that is NOT in target.allowed_hosts → safety policy refuses.
    # We invoke main so the outermost SentinelError handler maps the raised
    # UnsafeTargetError to its deterministic exit code (4).
    from sentinel_cli.main import main

    code = main(["discover", "--url", "https://example.com"])
    assert code == 4
