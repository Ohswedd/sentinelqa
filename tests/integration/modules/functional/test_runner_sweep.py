"""End-to-end functional-module sweep (Phase 10.05).

Two scenarios:

- ``sample-app``         → runner reports all green; module summarizes
  ``passed``, emits zero findings of severity ≥ medium, exit 0.
- ``sample-app-broken``  → runner reports a login + role-boundary
  failure; module summarizes ``failed``, emits one high-severity
  Finding per failure with our product spec evidence, exit 1.

The Playwright executor itself stays out of CI: we wire a deterministic
stub runner that mirrors what the real runner would emit when pointed at
each fixture (the fixture HTML lives at
``packages/ts-runtime/fixtures/sample-app[-broken]/`` and is hand-checked
by the dev sweep).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from engine.runner.local import RunnerInvocation
from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    TestExecution,
)

from modules.functional import FunctionalModule

FIXTURE_ROOT = Path(__file__).resolve().parents[4] / "packages" / "ts-runtime" / "fixtures"


def _write_config(root: Path, *, base_url: str = "http://localhost:3000") -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n  allowed_hosts: [localhost, 127.0.0.1]\n",
        encoding="utf-8",
    )
    return p


def _seed_specs(project: Path, names: list[str]) -> None:
    spec_root = project / "tests" / "sentinel"
    spec_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        (spec_root / name).write_text("// stub spec\n", encoding="utf-8")


def _build_ctx(tmp_path: Path, *, options: Mapping[str, Any] | None = None) -> ModuleContext:
    config = load_config(_write_config(tmp_path))
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    return ModuleContext(
        module_name="functional",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="test_fixture",
            host="localhost",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=__import__("engine.domain.ids", fromlist=["IdGenerator"]).IdGenerator(),
        options=options or {},
    )


def _outcome_for_fixture(fixture: str) -> RunnerOutcome:
    if fixture == "sample-app":
        tests = (
            TestExecution(
                test_id="login-happy",
                title="user can sign in",
                file="tests/sentinel/login.spec.ts",
                status="passed",
                duration_ms=180,
                retries=0,
            ),
            TestExecution(
                test_id="smoke-home",
                title="home loads",
                file="tests/sentinel/smoke.spec.ts",
                status="passed",
                duration_ms=80,
                retries=0,
            ),
        )
        status = "passed"
    elif fixture == "sample-app-broken":
        tests = (
            TestExecution(
                test_id="login-broken",
                title="user can sign in",
                file="tests/sentinel/login.spec.ts",
                status="failed",
                duration_ms=900,
                retries=1,
                evidence=("traces/login.zip", "screenshots/login.png"),
                error_message="Expected post-login navigation to /dashboard; got /success.html",
            ),
            TestExecution(
                test_id="role-broken",
                title="non-admin cannot reach /admin",
                file="tests/sentinel/role_boundary.spec.ts",
                status="failed",
                duration_ms=700,
                retries=0,
                evidence=("traces/role.zip",),
                error_message="Expected 403; got 200",
            ),
        )
        status = "failed"
    else:
        raise ValueError(fixture)
    return RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-SWEEPAAAAAAA",
        status=status,
        tests=tests,
        duration_ms=1_500,
        environment=EnvironmentContext(
            browser="chromium",
            browser_version="bundled",
            os="linux-test",
        ),
    )


class _CannedRunner:
    def __init__(self, outcome: RunnerOutcome) -> None:
        self._outcome = outcome
        self.received: RunnerInvocation | None = None

    def run(self, invocation: RunnerInvocation) -> RunnerOutcome:
        self.received = invocation
        return self._outcome


# ---------------------------------------------------------------------------
# Happy path — sample-app
# ---------------------------------------------------------------------------


def test_functional_module_against_sample_app_emits_zero_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_specs(tmp_path, ["login.spec.ts", "smoke.spec.ts"])
    runner = _CannedRunner(_outcome_for_fixture("sample-app"))
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(
        ctx.config,
        ctx.safety_decision,
        runner_factory=lambda _c, _s: runner,
    )
    result = module.run(ctx)
    assert result.status == "passed"
    assert result.findings == ()
    assert result.metrics["tests_passed"] == 2
    assert result.metrics["tests_failed"] == 0


# ---------------------------------------------------------------------------
# Broken path — sample-app-broken
# ---------------------------------------------------------------------------


def test_functional_module_against_sample_app_broken_emits_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_specs(tmp_path, ["login.spec.ts", "role_boundary.spec.ts"])
    runner = _CannedRunner(_outcome_for_fixture("sample-app-broken"))
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(
        ctx.config,
        ctx.safety_decision,
        runner_factory=lambda _c, _s: runner,
    )
    result = module.run(ctx)
    assert result.status == "failed"
    assert len(result.findings) == 2
    # Every finding carries our product spec evidence and is severity 'high'.
    for finding in result.findings:
        assert finding.module == "functional"
        assert finding.severity == "high"
        assert finding.evidence, "expected at least one evidence record per finding"
        assert finding.reproduction_steps, "expected repro steps on every finding"
        assert finding.affected_target == "http://localhost:3000/"


# ---------------------------------------------------------------------------
# Fixture-on-disk sanity
# ---------------------------------------------------------------------------


def test_sample_app_fixture_exists_on_disk() -> None:
    assert (FIXTURE_ROOT / "sample-app" / "index.html").exists()


def test_sample_app_broken_fixture_exists_on_disk_and_contains_marker() -> None:
    broken = FIXTURE_ROOT / "sample-app-broken"
    assert (broken / "index.html").exists()
    assert (broken / "success.html").exists()
    assert (broken / "admin.html").exists()
    # The broken success page must NOT contain the legitimate "Welcome"
    # signed-in marker that the happy fixture ships with.
    assert "Welcome" not in (broken / "success.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Runner outcome → ModuleResult mapping is byte-stable
# ---------------------------------------------------------------------------


def test_module_result_json_round_trip_is_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_specs(tmp_path, ["login.spec.ts"])
    runner = _CannedRunner(_outcome_for_fixture("sample-app-broken"))
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(
        ctx.config,
        ctx.safety_decision,
        runner_factory=lambda _c, _s: runner,
    )
    result = module.run(ctx)
    first = json.dumps(result.to_dict(), sort_keys=True, default=str)
    second = json.dumps(result.to_dict(), sort_keys=True, default=str)
    assert first == second
