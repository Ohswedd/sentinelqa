"""CLI integration tests for ``sentinel functional`` (Phase 10.04)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from engine.runner.local import RunnerInvocation
from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    TestExecution,
)
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


def _seed_specs(project: Path, names: list[str]) -> None:
    spec_root = project / "tests" / "sentinel"
    spec_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        (spec_root / name).write_text("// stub\n", encoding="utf-8")


def _build_outcome(*, failures: int = 0) -> RunnerOutcome:
    tests: list[TestExecution] = []
    for i in range(failures):
        tests.append(
            TestExecution(
                test_id=f"f-{i}",
                title=f"failing {i}",
                file=f"a-{i}.spec.ts",
                status="failed",
                duration_ms=500,
                retries=0,
                error_message="bad",
            )
        )
    if failures == 0:
        tests.append(
            TestExecution(
                test_id="ok",
                title="ok",
                file="ok.spec.ts",
                status="passed",
                duration_ms=120,
                retries=0,
            )
        )
    return RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-FUNCAAAAAAAA",
        status="failed" if failures > 0 else "passed",
        tests=tuple(tests),
        duration_ms=500 if failures > 0 else 120,
        environment=EnvironmentContext(
            browser="chromium",
            browser_version="bundled",
            os="linux-test",
        ),
    )


class _StubRunner:
    def __init__(self, outcome: RunnerOutcome) -> None:
        self._outcome = outcome
        self.received: RunnerInvocation | None = None

    def run(self, invocation: RunnerInvocation) -> RunnerOutcome:
        self.received = invocation
        return self._outcome


def _patch_runner(monkeypatch: pytest.MonkeyPatch, outcome: RunnerOutcome) -> _StubRunner:
    """Replace the registry factory so FunctionalModule receives a stub runner.

    Patching the module-level :func:`modules.functional.module._default_runner_factory`
    does NOT bypass :meth:`FunctionalModule.validate_prerequisites` (the
    module remembers whether it was constructed with a custom factory).
    Replacing :func:`_factory` lets us inject ``runner_factory=<stub>``
    via the constructor so the prerequisite probe is skipped.
    """

    runner = _StubRunner(outcome)
    from modules.functional.module import FunctionalModule

    def _stub_factory(cfg: Any, sd: Any) -> Any:
        return FunctionalModule(cfg, sd, runner_factory=lambda _c, _s: runner)

    monkeypatch.setattr("modules.functional.module._factory", _stub_factory)
    monkeypatch.setitem(
        __import__("engine.orchestrator.registry", fromlist=["default_registry"])
        .default_registry()
        .modules,
        "functional",
        _stub_factory,
    )
    return runner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_functional_command_passes_when_runner_reports_passed(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["happy.spec.ts"])
    runner = _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "module_status     : passed" in result.stdout
    assert runner.received is not None
    # Default mode → standard → grep "@p0|@p1"
    assert runner.received.grep == "@p0|@p1"


def test_functional_command_json_mode_emits_machine_readable_payload(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["happy.spec.ts"])
    _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["--json", "functional"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["command"] == "functional"
    assert payload["status"] == "passed"
    assert payload["module_status"] == "passed"
    assert payload["mode"] == "standard"


def test_functional_command_quiet_mode_emits_nothing_on_success(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["happy.spec.ts"])
    _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["--quiet", "functional"])
    assert result.exit_code == 0
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# Slice modes
# ---------------------------------------------------------------------------


def test_functional_command_smoke_mode_forwards_p0_grep(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["a.spec.ts"])
    runner = _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional", "--mode", "smoke"])
    assert result.exit_code == 0
    assert runner.received is not None
    assert runner.received.grep == "@p0"


def test_functional_command_full_mode_with_user_grep_forwards_verbatim(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["a.spec.ts"])
    runner = _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional", "--mode", "full", "--grep", "@flow:login"])
    assert result.exit_code == 0
    assert runner.received is not None
    assert runner.received.grep == "@flow:login"


def test_functional_command_unknown_mode_exits_2(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    cli = build_app()
    result = cli_runner.invoke(cli, ["functional", "--mode", "nope"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Failure / safety
# ---------------------------------------------------------------------------


def test_functional_command_quality_gate_failure_exits_1(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["broken.spec.ts"])
    _patch_runner(monkeypatch, _build_outcome(failures=2))

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional"])
    assert result.exit_code == 1, result.stdout + result.stderr


def test_functional_command_unsafe_target_exits_4(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    config_path = fresh_project / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\nproject:\n  name: app\n" "target:\n  base_url: https://example.com\n",
        encoding="utf-8",
    )
    _seed_specs(fresh_project, ["a.spec.ts"])

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional"])
    assert result.exit_code == 4, result.stdout + result.stderr


def test_functional_command_missing_config_exits_2(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    cli = build_app()
    result = cli_runner.invoke(cli, ["functional"])
    assert result.exit_code == 2


def test_functional_command_url_override_propagates(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["a.spec.ts"])
    runner = _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional", "--url", "http://localhost:9999"])
    assert result.exit_code == 0
    assert runner.received is not None
    assert runner.received.target.startswith("http://localhost:9999")


def test_functional_command_invalid_shard_exits_2(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    _seed_specs(fresh_project, ["a.spec.ts"])
    cli = build_app()
    result = cli_runner.invoke(cli, ["functional", "--shard", "not-a-shard"])
    assert result.exit_code == 2


def test_functional_command_no_specs_returns_skipped(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    write_config(fresh_project)
    # Patch the runner so we don't depend on sentinel-ts being installed.
    runner = _patch_runner(monkeypatch, _build_outcome())

    cli = build_app()
    result = cli_runner.invoke(cli, ["functional"])
    # No specs to run → the FunctionalModule returns an empty outcome and
    # the run reports module_status=skipped, exit_code 0.
    assert result.exit_code == 0
    assert "module_status     : skipped" in result.stdout
    assert runner.received is None
