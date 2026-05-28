"""CLI integration tests for ``sentinel security`` (Phase 13.12)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from modules.security.models import (
    SECURITY_RESULT_SCHEMA_VERSION,
    SecurityCheckResult,
    SecurityIssue,
    SecurityRunOutcome,
)
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


class _StubSecurityModule:
    """Returns a canned outcome regardless of inputs."""

    def __init__(self, outcome: SecurityRunOutcome) -> None:
        self._outcome = outcome

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from engine.orchestrator.registry import default_registry

        from modules.security.module import SecurityModule

        outcome = self._outcome

        def factory(cfg: Any, sd: Any) -> Any:
            module = SecurityModule(cfg, sd)

            def fake_run_audit(_ctx: Any) -> SecurityRunOutcome:
                return outcome

            module._run_audit = fake_run_audit  # type: ignore[method-assign,assignment]
            return module

        registry = default_registry()
        registry.modules["security"] = factory


def _outcome(
    *,
    issues: tuple[SecurityIssue, ...] = (),
    check: str = "headers",
) -> SecurityRunOutcome:
    return SecurityRunOutcome(
        schema_version=SECURITY_RESULT_SCHEMA_VERSION,
        checks=(
            SecurityCheckResult(
                check=check,
                targets_scanned=1,
                issues=issues,
                duration_ms=10,
            ),
        ),
        duration_ms=10,
    )


@pytest.fixture
def cli_app():
    return build_app()


def test_security_clean_returns_exit_zero(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSecurityModule(_outcome()).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "security", "--routes", "/", "--checks", "headers"])
    assert result.exit_code == 0, result.stderr


def test_security_with_high_finding_returns_quality_gate_failed(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    issue = SecurityIssue(
        rule_id="SEC-HEADERS-CSP-MISSING",
        severity="high",
        confidence=0.9,
        title="CSP missing",
        description="No CSP returned",
        route="/",
    )
    _StubSecurityModule(_outcome(issues=(issue,))).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "security", "--routes", "/", "--checks", "headers"])
    assert result.exit_code == 1, result.stderr


def test_security_json_mode_emits_machine_payload(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSecurityModule(_outcome()).install(monkeypatch)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "--json", "security", "--routes", "/", "--checks", "headers"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "security"
    assert payload["module_status"] in {"passed", "skipped"}


def test_security_unknown_check_returns_config_error(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "security", "--routes", "/", "--checks", "headers,nonexistent_check"],
    )
    assert result.exit_code == 2


def test_security_invalid_mode_returns_config_error(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "security", "--mode", "bogus"],
    )
    assert result.exit_code == 2


def test_security_unsafe_target_returns_exit_four(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Public target with no allowlist → safety policy refuses.
    config = tmp_path / "sentinel.config.yaml"
    config.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n  base_url: https://example.com\n  allowed_hosts: []\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli_app, ["--no-ci", "security", "--routes", "/"])
    assert result.exit_code == 4
