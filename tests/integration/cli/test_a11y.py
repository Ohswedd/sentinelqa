"""CLI integration tests for ``sentinel a11y``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from modules.accessibility.models import (
    A11yPageResult,
    AxeNode,
    AxeViolation,
)
from modules.accessibility.runner import A11yInvocation, A11yRunnerError, A11yRunOutcome
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


def _violation(rule_id: str, impact: str = "critical") -> AxeViolation:
    return AxeViolation(
        rule_id=rule_id,
        impact=impact,  # type: ignore[arg-type]
        help=f"{rule_id} help",
        help_url=f"https://example.test/{rule_id}",
        description=f"{rule_id} description",
        tags=("wcag2a",),
        nodes=(AxeNode(target=(f"img.{rule_id}",), html=f"<img class={rule_id}>"),),
    )


def _page(
    *,
    route: str = "/",
    violations: tuple[AxeViolation, ...] = (),
) -> A11yPageResult:
    return A11yPageResult(
        route=route,
        url=f"http://localhost:3000{route}",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=violations,
        duration_ms=10,
    )


class _StubA11yRunner:
    def __init__(self, outcome: A11yRunOutcome, *, raise_with: Exception | None = None) -> None:
        self._outcome = outcome
        self._raise_with = raise_with
        self.invocation: A11yInvocation | None = None

    def run(self, invocation: A11yInvocation) -> A11yRunOutcome:
        self.invocation = invocation
        if self._raise_with is not None:
            raise self._raise_with
        return self._outcome


def _patch_runner(
    monkeypatch: pytest.MonkeyPatch,
    outcome: A11yRunOutcome,
    *,
    raise_with: Exception | None = None,
) -> _StubA11yRunner:
    """Replace the registry factory so AccessibilityModule receives a stub runner."""

    stub = _StubA11yRunner(outcome, raise_with=raise_with)
    from modules.accessibility.module import AccessibilityModule

    def _stub_factory(cfg: Any, sd: Any) -> Any:
        return AccessibilityModule(cfg, sd, runner_factory=lambda _c, _s: stub)

    monkeypatch.setattr("modules.accessibility.module._factory", _stub_factory)
    monkeypatch.setitem(
        __import__("engine.orchestrator.registry", fromlist=["default_registry"])
        .default_registry()
        .modules,
        "accessibility",
        _stub_factory,
    )
    return stub


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_a11y_compliant_page_exits_zero(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(monkeypatch, A11yRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "module_status     : passed" in result.stdout
    assert stub.invocation is not None
    assert stub.invocation.routes == ("/",)


def test_a11y_routes_flag_passes_subset(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(
        monkeypatch,
        A11yRunOutcome(pages=(_page(), _page(route="/dashboard")), duration_ms=10),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y", "--routes", "/,/dashboard"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert stub.invocation is not None
    assert stub.invocation.routes == ("/", "/dashboard")


def test_a11y_axe_tags_override(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    stub = _patch_runner(monkeypatch, A11yRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y", "--axe-tags", "wcag21aa"])
    assert result.exit_code == 0
    assert stub.invocation is not None
    assert stub.invocation.axe_tags == ("wcag21aa",)


def test_a11y_json_mode_emits_machine_readable_payload(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(monkeypatch, A11yRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["--json", "a11y"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["command"] == "a11y"
    assert payload["module_status"] == "passed"
    assert payload["findings"] == 0


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_a11y_high_finding_blocks_with_exit_one(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    page = _page(violations=(_violation("image-alt", impact="critical"),))
    _patch_runner(monkeypatch, A11yRunOutcome(pages=(page,), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y"])
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "high_or_critical  : 1" in result.stdout


def test_a11y_sentinel_ts_missing_exits_five(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(
        monkeypatch,
        A11yRunOutcome(pages=(), duration_ms=0),
        raise_with=A11yRunnerError("sentinel-ts binary not found. Install @sentinelqa/ts-runtime."),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y"])
    assert result.exit_code == 5, result.stdout + result.stderr


def test_a11y_runner_failure_exits_six(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(
        monkeypatch,
        A11yRunOutcome(pages=(), duration_ms=0),
        raise_with=A11yRunnerError("Chromium crashed mid-route"),
    )

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y"])
    assert result.exit_code == 6, result.stdout + result.stderr


def test_a11y_invalid_routes_argument_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y", "--routes", " , , "])
    assert result.exit_code == 2, result.stdout + (result.stderr or "")


def test_a11y_invalid_axe_tags_argument_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y", "--axe-tags", ", ,"])
    assert result.exit_code == 2, result.stdout + result.stderr


def test_a11y_unsafe_target_exits_four(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(monkeypatch, A11yRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y", "--url", "https://example.test"])
    assert result.exit_code == 4, result.stdout + result.stderr


def test_a11y_url_override_changes_target_base_url(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project, base_url="http://localhost:3000")
    stub = _patch_runner(monkeypatch, A11yRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y", "--url", "http://127.0.0.1:5000"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert stub.invocation is not None
    assert stub.invocation.target == "http://127.0.0.1:5000/"


def test_a11y_quiet_mode_emits_nothing_on_success(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _patch_runner(monkeypatch, A11yRunOutcome(pages=(_page(),), duration_ms=10))

    cli = build_app()
    result = cli_runner.invoke(cli, ["--quiet", "a11y"])
    assert result.exit_code == 0
    assert result.stdout == ""


def test_a11y_config_load_error_exits_two(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    # No config file at all.
    cli = build_app()
    result = cli_runner.invoke(cli, ["a11y"])
    assert result.exit_code == 2, result.stdout + result.stderr
