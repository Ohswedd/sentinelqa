"""CLI integration tests for ``sentinel api`` (Phase 22.09)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
    ApiRunOutcome,
)
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


class _StubApiModule:
    """Patch ApiModule._run_audit so the CLI runs deterministically."""

    def __init__(self, outcome: ApiRunOutcome) -> None:
        self._outcome = outcome

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from engine.orchestrator.registry import default_registry

        from modules.api.module import ApiModule

        outcome = self._outcome

        def factory(cfg: Any, sd: Any) -> Any:
            module = ApiModule(cfg, sd)

            def fake_run_audit(_ctx: Any) -> ApiRunOutcome:
                return outcome

            module._run_audit = fake_run_audit  # type: ignore[method-assign,assignment]
            return module

        registry = default_registry()
        registry.modules["api"] = factory


def _outcome(*, issues: tuple[ApiIssue, ...] = ()) -> ApiRunOutcome:
    return ApiRunOutcome(
        schema_version=API_RESULT_SCHEMA_VERSION,
        checks=(
            ApiCheckResult(
                schema_version=API_RESULT_SCHEMA_VERSION,
                check="contract",
                issues=issues,
                targets_scanned=1,
                duration_ms=10,
            ),
        ),
        duration_ms=10,
    )


@pytest.fixture
def cli_app():
    return build_app()


def test_api_clean_returns_exit_zero(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubApiModule(_outcome()).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "api", "--checks", "contract"])
    assert result.exit_code == 0, result.stderr


def test_api_high_finding_returns_quality_gate_failed(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    issue = ApiIssue(
        rule_id="CONTRACT-SCHEMA",
        severity="high",
        confidence=0.9,
        title="schema mismatch",
        description="response missing required field",
        method="GET",
        route="/items",
        recommendation="fix",
    )
    _StubApiModule(_outcome(issues=(issue,))).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "api", "--checks", "contract"])
    assert result.exit_code == 1, result.stderr


def test_api_json_mode_emits_machine_payload(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubApiModule(_outcome()).install(monkeypatch)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "--json", "api", "--checks", "contract"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "api"
    assert "run_id" in payload
    assert payload["module_status"] in {"passed", "skipped"}


def test_api_unknown_check_returns_config_error(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "api", "--checks", "contract,bogus_check"],
    )
    assert result.exit_code == 2


def test_api_unsafe_target_returns_exit_four(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "sentinel.config.yaml"
    config.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n  base_url: https://example.com\n  allowed_hosts: []\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["--no-ci", "api"])
    assert result.exit_code == 4


def test_api_help_lists_supported_flags_and_no_forbidden_ones(cli_app, runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["api", "--help"])
    assert result.exit_code == 0
    help_text = result.stdout
    for expected in ("--url", "--openapi", "--graphql", "--checks", "--diff-since"):
        assert expected in help_text, f"missing {expected!r} in --help"
    for forbidden in ("--aggressive", "--fuzz", "--brute", "--unbounded"):
        assert forbidden not in help_text, f"forbidden flag {forbidden!r} surfaced"
