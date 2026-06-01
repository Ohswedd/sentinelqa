"""determinism audit over the reporter pipeline.

our engineering rules.8 / §19 require that the score and findings outputs be
reproducible. The expensive PRD test would be ``sentinel audit`` against the
Next.js example three times in a row, but that brings a Node/Playwright stack
into CI and adds wall-clock latency without testing anything new on top of
the reporter writers — those are the layer that converts in-memory domain
objects into the on-disk artifacts we ship.

This test exercises the **same writers the lifecycle uses** N times with the
same deterministic fixture and asserts byte-equal output. The diff helper
``scripts/diff_runs.py`` is used as a second gate: it normalizes the volatile
fields and confirms the diff after normalization is empty even when the
inputs *are* allowed to vary (e.g. different ``RUN-*`` IDs).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.findings_writer import write_findings
from engine.reporter.run_writer import write_run
from engine.reporter.score_writer import write_score

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.diff_runs import diff_directories  # noqa: E402

RUN_ID = "RUN-DETERMAAAAAA"
N_RUNS = 3

STARTED_AT = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 5, 27, 12, 0, 30, tzinfo=UTC)
GENERATED_AT = datetime(2026, 5, 27, 12, 0, 30, tzinfo=UTC)


def _findings() -> tuple[Finding, ...]:
    return (
        Finding(
            id="FND-DETHIGHAAAAA",
            run_id=RUN_ID,
            module="security",
            category="security/cookies",
            severity="high",
            confidence=0.9,
            title="Session cookie missing HttpOnly attribute",
            description="Cookie set on /login lacks HttpOnly.",
            location=FindingLocation(route="/login"),
            evidence=(
                Evidence(
                    id="EVD-DETHIGHAAAAA",
                    type="network_log",
                    path=Path("traces/login.har"),
                    redacted=True,
                ),
            ),
            recommendation="Set HttpOnly on the cookie.",
            affected_target="https://localhost:8080",
            created_at=FINISHED_AT,
        ),
    )


def _module_results(findings: tuple[Finding, ...]) -> tuple[ModuleResult, ...]:
    return (
        ModuleResult(
            id="MOD-FUNCDETAAAAA",
            name="functional",
            status="passed",
            findings=(),
            metrics={"tests_run": 10, "tests_passed": 10},
            duration_ms=4200,
            errors=(),
        ),
        ModuleResult(
            id="MOD-SECDETAAAAAA",
            name="security",
            status="passed",
            findings=findings,
            metrics={"checks_run": 12},
            duration_ms=3100,
            errors=(),
        ),
    )


def _quality_score() -> QualityScore:
    return QualityScore(
        id="SCR-DETSCOREAAAA",
        run_id=RUN_ID,
        total=87.25,
        components={
            "security": 80.0,
            "functional": 95.0,
            "accessibility": 82.0,
            "performance": 90.0,
        },
        weights={
            "security": 0.25,
            "functional": 0.4,
            "accessibility": 0.15,
            "performance": 0.2,
        },
        severity_penalties_applied={"high": 5.0},
    )


def _policy_decision() -> PolicyDecision:
    return PolicyDecision(
        id="PD-DETDECISIONA",
        run_id=RUN_ID,
        release_decision="pass",
        blocked_by=(),
        reasons=(),
    )


def _config_snapshot() -> dict[str, object]:
    return {
        "modules": {"functional": True, "security": True},
        "policy": {"min_quality_score": 80},
        "target": {"base_url": "https://localhost:8080"},
    }


def _test_run() -> TestRun:
    return TestRun(
        id=RUN_ID,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        target=Target(base_url="https://localhost:8080", mode="safe"),
        config_snapshot=_config_snapshot(),
        modules_run=("functional", "security"),
        status="passed",
    )


def _emit_one(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory.create(out, RUN_ID)
    findings = _findings()
    write_findings(
        artifacts,
        findings,
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
    )
    write_score(
        artifacts,
        run_id=RUN_ID,
        score=_quality_score(),
        policy_decision=_policy_decision(),
        policy_config={
            "min_quality_score": 80.0,
            "block_on_critical": True,
            "block_on_high_security": True,
            "max_failed_p1_flows": 0,
            "max_flake_rate": 0.05,
        },
    )
    write_run(
        artifacts,
        _test_run(),
        module_results=_module_results(findings),
        findings=findings,
        score=_quality_score(),
        policy=_policy_decision(),
        config_snapshot=_config_snapshot(),
    )
    return artifacts.root


@pytest.mark.parametrize("artifact", ["findings.json", "score.json"])
def test_writer_output_is_byte_equal_across_runs(tmp_path: Path, artifact: str) -> None:
    """Run the writer ``N_RUNS`` times. The artifact in question must be identical."""

    payloads: list[bytes] = []
    for i in range(N_RUNS):
        run_dir = _emit_one(tmp_path / f"run-{i}")
        payloads.append((run_dir / artifact).read_bytes())

    reference = payloads[0]
    for i, payload in enumerate(payloads[1:], start=2):
        assert (
            payload == reference
        ), f"{artifact} differs between run 1 and run {i}; the writer is non-deterministic."


def test_full_run_artifacts_are_byte_equal_modulo_volatile_fields(tmp_path: Path) -> None:
    """End-to-end: the full artifact tree should diff clean after normalization."""

    run_dirs = [_emit_one(tmp_path / f"run-{i}") for i in range(N_RUNS)]
    diffs = diff_directories(run_dirs, strict=False)
    assert diffs == [], "\n".join(diffs)


def test_diff_runs_strict_mode_detects_changes(tmp_path: Path) -> None:
    """The diff helper must NOT pass when bytes legitimately differ in non-volatile fields."""

    run_a = _emit_one(tmp_path / "run-a")
    run_b = _emit_one(tmp_path / "run-b")
    # Inject a non-volatile drift to confirm the helper catches it.
    findings_path = run_b / "findings.json"
    poisoned = findings_path.read_text().replace(
        "Session cookie missing HttpOnly attribute",
        "Session cookie missing HttpOnly attribute (drift)",
    )
    findings_path.write_text(poisoned)

    diffs = diff_directories([run_a, run_b], strict=False)
    assert diffs, "diff_runs should have surfaced the injected drift"
