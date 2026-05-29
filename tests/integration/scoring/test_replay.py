"""Task 14.05 — score-replay regression test.

Three canonical scenarios — a clean run, a run with mixed-severity
findings, and a blocked-by-critical run — are computed end-to-end and
compared against committed expected payloads. The artifact bytes must
match exactly so any drift in the scoring math fails fast in CI.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.config.schema import PolicyConfig
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.module_result import ModuleResult
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.score_writer import write_score
from engine.scoring.policy_gate import apply_policy_gate

REPLAY_RUN_ID = "RUN-REPLAYAAAAAA"
REPLAY_TS = datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)
EXPECTED_DIR = Path(__file__).parent / "expected"
GOLDEN_UPDATE_ENV = "SENTINELQA_UPDATE_GOLDENS"


def _evidence(suffix: str) -> tuple[Evidence, ...]:
    return (
        Evidence(
            id=f"EVD-{suffix}",
            type="source_ref",
            path=Path(f"evidence/{suffix}.txt"),
            redacted=True,
        ),
    )


def _finding(
    *,
    id_suffix: str,
    module: str,
    severity: Severity,
    title: str,
) -> Finding:
    return Finding(
        id=f"FND-{id_suffix}",
        run_id=REPLAY_RUN_ID,
        module=module,
        category=f"{module}/replay",
        severity=severity,
        confidence=0.9,
        title=title,
        description=f"Replay canonical finding for {module}/{severity}.",
        location=FindingLocation(),
        evidence=_evidence(id_suffix) if severity in {"critical", "high", "medium"} else (),
        recommendation="Fix it.",
        affected_target="http://localhost:3000",
        created_at=REPLAY_TS,
    )


def _module(*, id_suffix: str, name: str, flake_rate: float | None = None) -> ModuleResult:
    metrics: dict[str, float | int] = {"tests_run": 5}
    if flake_rate is not None:
        metrics["flake_rate"] = flake_rate
    return ModuleResult(
        id=f"MOD-{id_suffix}",
        name=name,
        status="passed",
        findings=(),
        metrics=metrics,
        duration_ms=1000,
        errors=(),
    )


CASES: Mapping[str, dict] = {
    "clean": {
        "findings": (),
        "modules": (
            _module(id_suffix="FUNCAAAAAAAA", name="functional", flake_rate=0.0),
            _module(id_suffix="SECCAAAAAAAA", name="security", flake_rate=0.0),
        ),
        "policy": PolicyConfig(),
        "run_status": "passed",
    },
    "mixed": {
        "findings": (
            _finding(
                id_suffix="HIGHSECAAAAA",
                module="security",
                severity="high",
                title="@p2 session cookie HttpOnly missing",
            ),
            _finding(
                id_suffix="MEDA11YAAAAA",
                module="accessibility",
                severity="medium",
                title="@p3 contrast on submit button",
            ),
            _finding(
                id_suffix="INFOPERFAAAA",
                module="performance",
                severity="info",
                title="LCP within budget",
            ),
        ),
        "modules": (
            _module(id_suffix="FUNCAAAAAAAA", name="functional", flake_rate=0.005),
            _module(id_suffix="SECCAAAAAAAA", name="security", flake_rate=0.0),
            _module(id_suffix="A11YAAAAAAAA", name="accessibility"),
        ),
        "policy": PolicyConfig(),
        "run_status": "passed",
    },
    "blocked": {
        "findings": (
            _finding(
                id_suffix="CRITSECAAAAA",
                module="security",
                severity="critical",
                title="Plaintext credentials in repo",
            ),
            _finding(
                id_suffix="P0LOGINAAAAA",
                module="functional",
                severity="high",
                title="@p0 login flow broken",
            ),
        ),
        "modules": (
            _module(id_suffix="FUNCAAAAAAAA", name="functional", flake_rate=0.02),
            _module(id_suffix="SECCAAAAAAAA", name="security", flake_rate=0.0),
        ),
        "policy": PolicyConfig(),
        "run_status": "passed",
    },
}


def _emit(case_name: str) -> bytes:
    case = CASES[case_name]
    with tempfile.TemporaryDirectory(prefix=f"sentinelqa-replay-{case_name}-") as tmp:
        artifacts = ArtifactDirectory.create(Path(tmp), REPLAY_RUN_ID)
        score, decision, _ = apply_policy_gate(
            case["findings"],
            case["modules"],
            policy=case["policy"],
            run_id=REPLAY_RUN_ID,
            run_status=case["run_status"],
        )
        path = write_score(
            artifacts,
            run_id=REPLAY_RUN_ID,
            score=score,
            policy_decision=decision,
            policy_config=case["policy"].to_dict(),
        )
        return path.read_bytes()


def _expected_path(case_name: str) -> Path:
    return EXPECTED_DIR / f"score.{case_name}.json"


def _golden_update_requested() -> bool:
    return os.environ.get(GOLDEN_UPDATE_ENV, "0") in {"1", "true", "TRUE", "yes"}


@pytest.mark.parametrize("case_name", sorted(CASES.keys()))
def test_canonical_score_replay(case_name: str) -> None:
    actual = _emit(case_name)
    expected_path = _expected_path(case_name)
    if _golden_update_requested():
        EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
        expected_path.write_bytes(actual)
        return
    assert expected_path.exists(), (
        f"Expected score replay golden missing: {expected_path}. "
        f"Run `{GOLDEN_UPDATE_ENV}=1 pytest tests/integration/scoring` to generate it."
    )
    expected = expected_path.read_bytes()
    if actual != expected:
        raise AssertionError(
            f"Score replay mismatch for {case_name!r}; "
            f"re-run with `{GOLDEN_UPDATE_ENV}=1` after reviewing the diff.\n"
            f"--- actual ---\n{actual.decode('utf-8')}\n"
            f"--- expected ---\n{expected.decode('utf-8')}"
        )


def test_replay_is_byte_stable_across_invocations() -> None:
    """A second emit of the same canonical inputs must equal the first."""

    for name in CASES:
        first = _emit(name)
        second = _emit(name)
        assert first == second, f"non-deterministic emit for case {name!r}"
        # Sanity: parsed JSON also matches.
        assert json.loads(first) == json.loads(second)
