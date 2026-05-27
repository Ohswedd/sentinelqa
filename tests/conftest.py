"""Shared pytest fixtures and helpers for the test suite.

Phase 03 introduces deterministic :class:`TestRun` / :class:`Finding` /
:class:`QualityScore` / :class:`PolicyDecision` / :class:`ModuleResult`
fixtures so every writer + golden test starts from the same canonical
inputs. Promoting them to the root ``tests/conftest.py`` keeps unit,
integration, and golden tests on a single set of fixtures (CLAUDE.md §16).

Golden semantics (CLAUDE.md §17): a writer test compares the actual bytes
against a committed golden file. Setting ``SENTINELQA_UPDATE_GOLDENS=1``
(or ``make update-goldens``) rewrites the golden in place so the diff
shows up in review.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.target import Target
from engine.domain.test_run import TestRun

GOLDEN_UPDATE_ENV: str = "SENTINELQA_UPDATE_GOLDENS"

# Deterministic IDs. ID_REGEX allows any ``[A-Z0-9]{12}`` after the prefix,
# so these literals pick mnemonic spellings that pad to exactly 12 chars.
RUN_ID = "RUN-PASSEDAAAAAA"
RUN_ID_2 = "RUN-DRYRUNAAAAAA"
RUN_ID_3 = "RUN-UNSAFEAAAAAA"


@pytest.fixture
def fixture_started_at() -> datetime:
    return datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def fixture_finished_at() -> datetime:
    return datetime(2026, 5, 27, 12, 0, 30, tzinfo=UTC)


@pytest.fixture
def fixture_config_snapshot() -> dict[str, Any]:
    return {
        "modules": {
            "functional": True,
            "accessibility": True,
        },
        "policy": {"min_quality_score": 80},
        "target": {"base_url": "https://localhost:8080"},
    }


@pytest.fixture
def fixture_target() -> Target:
    return Target(base_url="https://localhost:8080", mode="safe")


@pytest.fixture
def fixture_test_run_passed(
    fixture_target: Target,
    fixture_started_at: datetime,
    fixture_finished_at: datetime,
    fixture_config_snapshot: dict[str, Any],
) -> TestRun:
    return TestRun(
        id=RUN_ID,
        started_at=fixture_started_at,
        finished_at=fixture_finished_at,
        target=fixture_target,
        config_snapshot=fixture_config_snapshot,
        modules_run=("accessibility", "functional"),
        status="passed",
    )


@pytest.fixture
def fixture_test_run_unsafe(
    fixture_target: Target,
    fixture_started_at: datetime,
    fixture_finished_at: datetime,
    fixture_config_snapshot: dict[str, Any],
) -> TestRun:
    return TestRun(
        id=RUN_ID_3,
        started_at=fixture_started_at,
        finished_at=fixture_finished_at,
        target=fixture_target,
        config_snapshot=fixture_config_snapshot,
        modules_run=(),
        status="unsafe_blocked",
    )


@pytest.fixture
def fixture_test_run_dry(
    fixture_target: Target,
    fixture_started_at: datetime,
    fixture_finished_at: datetime,
    fixture_config_snapshot: dict[str, Any],
) -> TestRun:
    return TestRun(
        id=RUN_ID_2,
        started_at=fixture_started_at,
        finished_at=fixture_finished_at,
        target=fixture_target,
        config_snapshot=fixture_config_snapshot,
        modules_run=("accessibility", "functional"),
        status="dry_run",
    )


@pytest.fixture
def fixture_findings_critical(fixture_finished_at: datetime) -> tuple[Finding, ...]:
    return (
        Finding(
            id="FND-CRITAAAAAAAA",
            run_id=RUN_ID,
            module="security",
            category="security/headers",
            severity="critical",
            confidence=0.95,
            title="Session cookie missing Secure flag",
            description=(
                "The session cookie returned from POST /login is set without the "
                "Secure attribute. On a non-HTTPS request the cookie would be "
                "transmitted in cleartext."
            ),
            location=FindingLocation(route="/login", selector=None, file=None, line=None),
            evidence=(
                Evidence(
                    id="EVD-CRITAAAAAAAA",
                    type="network_log",
                    path=Path("traces/login.har"),
                    redacted=True,
                ),
            ),
            reproduction_steps=(
                "POST https://localhost:8080/login with valid credentials.",
                "Inspect the Set-Cookie response header — note the missing Secure flag.",
            ),
            recommendation="Set the Secure attribute on the session cookie.",
            affected_target="https://localhost:8080",
            created_at=fixture_finished_at,
        ),
    )


@pytest.fixture
def fixture_findings_mixed(fixture_finished_at: datetime) -> tuple[Finding, ...]:
    return (
        Finding(
            id="FND-HIGHAAAAAAAA",
            run_id=RUN_ID,
            module="security",
            category="security/cookies",
            severity="high",
            confidence=0.9,
            title="Session cookie missing HttpOnly attribute",
            description=(
                "The session cookie on /login is missing HttpOnly; client-side "
                "JavaScript can read it."
            ),
            location=FindingLocation(route="/login"),
            evidence=(
                Evidence(
                    id="EVD-HIGHAAAAAAAA",
                    type="network_log",
                    path=Path("traces/login.har"),
                    redacted=True,
                ),
            ),
            recommendation="Set HttpOnly on the session cookie.",
            affected_target="https://localhost:8080",
            created_at=fixture_finished_at,
        ),
        Finding(
            id="FND-MEDAAAAAAAAA",
            run_id=RUN_ID,
            module="accessibility",
            category="a11y/contrast",
            severity="medium",
            confidence=0.7,
            title="Insufficient contrast on submit button",
            description="The /signup submit button has contrast ratio 3.8 (WCAG AA needs ≥4.5).",
            location=FindingLocation(route="/signup", selector="button[type=submit]"),
            evidence=(
                Evidence(
                    id="EVD-MEDAAAAAAAAA",
                    type="screenshot",
                    path=Path("screenshots/signup.png"),
                    redacted=True,
                ),
            ),
            recommendation="Increase foreground/background contrast to ≥4.5.",
            affected_target="https://localhost:8080",
            created_at=fixture_finished_at,
        ),
        Finding(
            id="FND-INFOAAAAAAAB",
            run_id=RUN_ID,
            module="performance",
            category="perf/lcp",
            severity="info",
            confidence=0.6,
            title="LCP within budget",
            description="LCP measured at 1.8s; budget is 2.5s.",
            location=FindingLocation(route="/"),
            evidence=(
                Evidence(
                    id="EVD-INFOAAAAAAAB",
                    type="trace",
                    path=Path("traces/home.zip"),
                    redacted=True,
                ),
            ),
            recommendation="No action required.",
            affected_target="https://localhost:8080",
            created_at=fixture_finished_at,
        ),
    )


@pytest.fixture
def fixture_module_results_passing(
    fixture_findings_mixed: tuple[Finding, ...],
) -> tuple[ModuleResult, ...]:
    return (
        ModuleResult(
            id="MOD-FUNCAAAAAAAA",
            name="functional",
            status="passed",
            findings=(),
            metrics={"tests_run": 12, "tests_passed": 12},
            duration_ms=4200,
            errors=(),
        ),
        ModuleResult(
            id="MOD-ACCAAAAAAAAA",
            name="accessibility",
            status="passed",
            findings=tuple(f for f in fixture_findings_mixed if f.module == "accessibility"),
            metrics={"violations": 1},
            duration_ms=2100,
            errors=(),
        ),
    )


@pytest.fixture
def fixture_module_results_blocked() -> tuple[ModuleResult, ...]:
    return (
        ModuleResult(
            id="MOD-FUNCAAAAAAAA",
            name="functional",
            status="failed",
            findings=(),
            metrics={"tests_run": 12, "tests_failed": 3},
            duration_ms=5200,
            errors=(),
        ),
        ModuleResult(
            id="MOD-ACCAAAAAAAAA",
            name="accessibility",
            status="errored",
            findings=(),
            metrics={},
            duration_ms=300,
            errors=("axe-core failed to load",),
        ),
        ModuleResult(
            id="MOD-PERFAAAAAAAA",
            name="performance",
            status="skipped",
            findings=(),
            metrics={},
            duration_ms=0,
            errors=(),
        ),
    )


@pytest.fixture
def fixture_quality_score_passing() -> QualityScore:
    return QualityScore(
        id="SCR-PASSAAAAAAAA",
        run_id=RUN_ID,
        total=87.25,
        components={
            "functional": 95.0,
            "accessibility": 82.0,
            "performance": 90.0,
            "security": 80.0,
        },
        weights={
            "functional": 0.4,
            "accessibility": 0.2,
            "performance": 0.2,
            "security": 0.2,
        },
        severity_penalties_applied={"medium": 5.0, "info": 0.0},
    )


@pytest.fixture
def fixture_quality_score_blocked() -> QualityScore:
    return QualityScore(
        id="SCR-BLKAAAAAAAAA",
        run_id=RUN_ID,
        total=42.5,
        components={
            "functional": 40.0,
            "accessibility": 50.0,
            "performance": 60.0,
            "security": 20.0,
        },
        weights={
            "functional": 0.4,
            "accessibility": 0.2,
            "performance": 0.2,
            "security": 0.2,
        },
        severity_penalties_applied={"critical": 40.0, "high": 15.0},
    )


@pytest.fixture
def fixture_policy_decision_pass() -> PolicyDecision:
    return PolicyDecision(
        id="PD-PASSAAAAAAAA",
        run_id=RUN_ID,
        release_decision="pass",
        blocked_by=(),
        reasons=("All gates green; quality_score=87.25 >= min 80.",),
    )


@pytest.fixture
def fixture_policy_decision_blocked() -> PolicyDecision:
    return PolicyDecision(
        id="PD-BLKAAAAAAAAA",
        run_id=RUN_ID,
        release_decision="blocked",
        blocked_by=("FND-CRITAAAAAAAA",),
        reasons=("Critical finding present.", "Quality score below minimum (42.5 < 80)."),
    )


# ---------------------------------------------------------------------------
# Golden helpers
# ---------------------------------------------------------------------------


def golden_should_update() -> bool:
    return os.environ.get(GOLDEN_UPDATE_ENV, "0") in {"1", "true", "TRUE", "yes"}


def assert_matches_golden(
    actual: str,
    golden_path: Path,
) -> None:
    """Compare ``actual`` text against ``golden_path``.

    If :data:`GOLDEN_UPDATE_ENV` is set, ``golden_path`` is rewritten in
    place and the comparison is skipped. Otherwise, the test fails on any
    mismatch. The error message is friendly so reviewers spot drift fast.
    """

    if golden_should_update():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual, encoding="utf-8")
        return
    assert golden_path.exists(), (
        f"Golden file missing: {golden_path}. "
        f"Run `{GOLDEN_UPDATE_ENV}=1 pytest {golden_path.parent.parent}` or "
        f"`make update-goldens` to generate it."
    )
    expected = golden_path.read_text(encoding="utf-8")
    if actual != expected:
        msg = (
            f"Golden mismatch at {golden_path}; " f"re-run with `{GOLDEN_UPDATE_ENV}=1` to update."
        )
        raise AssertionError(msg + f"\n--- actual ---\n{actual}\n--- expected ---\n{expected}")


@pytest.fixture
def goldens_root() -> Path:
    return Path(__file__).parent / "golden" / "reports"


__all__ = [
    "GOLDEN_UPDATE_ENV",
    "RUN_ID",
    "RUN_ID_2",
    "RUN_ID_3",
    "assert_matches_golden",
    "golden_should_update",
]
