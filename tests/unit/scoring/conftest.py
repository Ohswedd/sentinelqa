"""Shared fixtures for Phase-14 scoring tests.

Builds a minimal ``RootConfig`` + ``PolicyConfig`` so scoring code can
be exercised in isolation, plus a small helper that constructs
deterministic Finding / ModuleResult objects without re-typing the
boilerplate the global conftest already supplies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.config.schema import (
    PolicyConfig,
    ProjectConfig,
    RootConfig,
    TargetConfig,
)
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.module_result import ModuleResult

SCORING_RUN_ID = "RUN-SCORINGAAAAA"
SCORING_CREATED_AT = datetime(2026, 5, 28, 9, 0, 0, tzinfo=UTC)


@pytest.fixture
def policy_defaults() -> PolicyConfig:
    return PolicyConfig()


@pytest.fixture
def policy_lenient() -> PolicyConfig:
    return PolicyConfig(
        min_quality_score=50,
        block_on_critical=False,
        block_on_high_security=False,
        max_failed_p1_flows=10,
    )


@pytest.fixture
def root_config_defaults() -> RootConfig:
    return RootConfig(
        project=ProjectConfig(name="scoring-fixture"),
        target=TargetConfig(base_url="http://localhost:3000"),
    )


def _pad12(suffix: str) -> str:
    """Pad/truncate a caller-supplied id suffix to 12 [A-Z0-9] chars."""

    cleaned = "".join(c if c.isalnum() else "X" for c in suffix.upper())
    return (cleaned + "X" * 12)[:12]


def make_finding(
    *,
    id: str,
    module: str,
    severity: Severity,
    title: str = "scoring fixture",
    description: str = "scoring fixture finding for scoring unit tests.",
    run_id: str = SCORING_RUN_ID,
    location: FindingLocation | None = None,
) -> Finding:
    # Normalise the caller-supplied id so any mnemonic suffix is valid.
    suffix = _pad12(id.split("-")[-1])
    fid = f"FND-{suffix}"
    evidence: tuple[Evidence, ...] = ()
    if severity in {"critical", "high", "medium"}:
        evidence = (
            Evidence(
                id=f"EVD-{suffix}",
                type="source_ref",
                path=Path(f"evidence/{fid}.txt"),
                redacted=True,
            ),
        )
    return Finding(
        id=fid,
        run_id=run_id,
        module=module,
        category=f"{module}/test",
        severity=severity,
        confidence=0.9,
        title=title,
        description=description,
        location=location or FindingLocation(),
        evidence=evidence,
        recommendation="Fix it in the relevant module.",
        affected_target="http://localhost:3000",
        created_at=SCORING_CREATED_AT,
    )


def make_module_result(
    *,
    id: str,
    name: str,
    status: str = "passed",
    findings: tuple[Finding, ...] = (),
    flake_rate: float | None = None,
) -> ModuleResult:
    metrics: dict[str, float | int] = {"tests_run": len(findings)}
    if flake_rate is not None:
        metrics["flake_rate"] = flake_rate
    return ModuleResult(
        id=id,
        name=name,
        status=status,  # type: ignore[arg-type]
        findings=findings,
        metrics=metrics,
        duration_ms=1000,
        errors=(),
    )


__all__ = [
    "SCORING_CREATED_AT",
    "SCORING_RUN_ID",
    "make_finding",
    "make_module_result",
]
