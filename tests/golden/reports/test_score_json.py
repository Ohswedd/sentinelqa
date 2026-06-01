"""Golden tests for ``score.json`` (task 03.03).

Covers the five canonical states from the task spec:

- passing run (PolicyDecision: pass)
- blocked-on-critical (PolicyDecision: blocked + blockers populated)
- passing-with-warnings (PolicyDecision: pass_with_warnings)
- unsafe_blocked (score null, release_decision unsafe_target_rejected)
- dry_run (score null, release_decision inconclusive)

Also locks the deterministic-float contract: a `0.1 + 0.2`-style total
must round to the same string on every call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.score_writer import write_score

from tests.conftest import RUN_ID, RUN_ID_2, RUN_ID_3, assert_matches_golden

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "shared-schema" / "score.schema.json"


@pytest.fixture
def score_schema() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return payload


# Same policy config every golden uses, so the diffs are minimal.
POLICY_CONFIG = {
    "min_quality_score": 80,
    "block_on_critical": True,
    "block_on_high_security": True,
    "max_failed_p1_flows": 0,
    "max_flake_rate": 0.05,
}


def test_score_golden_pass(
    tmp_path: Path,
    goldens_root: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
        policy_config=POLICY_CONFIG,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "score.pass.golden.json")


def test_score_golden_blocked(
    tmp_path: Path,
    goldens_root: Path,
    fixture_quality_score_blocked: QualityScore,
    fixture_policy_decision_blocked: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_blocked,
        policy_decision=fixture_policy_decision_blocked,
        policy_config=POLICY_CONFIG,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "score.blocked.golden.json")


def test_score_golden_pass_with_warnings(
    tmp_path: Path,
    goldens_root: Path,
    fixture_quality_score_passing: QualityScore,
) -> None:
    policy = PolicyDecision(
        id="PD-WARNAAAAAAAA",
        run_id=RUN_ID,
        release_decision="pass_with_warnings",
        blocked_by=(),
        reasons=("Two medium findings present but score above threshold.",),
    )
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=policy,
        policy_config=POLICY_CONFIG,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "score.warnings.golden.json")


def test_score_golden_unsafe(
    tmp_path: Path,
    goldens_root: Path,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID_3)
    written = write_score(
        artifacts,
        run_id=RUN_ID_3,
        score=None,
        policy_decision=None,
        release_decision="unsafe_target_rejected",
        policy_config=POLICY_CONFIG,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "score.unsafe.golden.json")


def test_score_golden_dry_run(
    tmp_path: Path,
    goldens_root: Path,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID_2)
    written = write_score(
        artifacts,
        run_id=RUN_ID_2,
        score=None,
        policy_decision=None,
        release_decision="inconclusive",
        policy_config=POLICY_CONFIG,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "score.dry_run.golden.json")


@pytest.mark.parametrize(
    "golden_name",
    [
        "score.pass.golden.json",
        "score.blocked.golden.json",
        "score.warnings.golden.json",
        "score.unsafe.golden.json",
        "score.dry_run.golden.json",
    ],
)
def test_score_golden_validates_against_schema(
    goldens_root: Path,
    score_schema: dict[str, Any],
    golden_name: str,
) -> None:
    golden_path = goldens_root / golden_name
    if not golden_path.exists():
        pytest.skip(f"Golden {golden_name} not generated (run with SENTINELQA_UPDATE_GOLDENS=1).")
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, score_schema)


def test_score_total_is_deterministic_under_float_arithmetic(
    tmp_path: Path,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    """0.1 + 0.2 must not corrupt the persisted total."""
    qs1 = QualityScore(
        id="SCR-DETAAAAAAAAA",
        run_id=RUN_ID,
        total=0.1 + 0.2,
        components={},
        weights={},
        severity_penalties_applied={},
    )
    qs2 = QualityScore(
        id="SCR-DETBBBBBBBBB",
        run_id=RUN_ID,
        total=0.3,
        components={},
        weights={},
        severity_penalties_applied={},
    )
    a = ArtifactDirectory.create(tmp_path / "a", RUN_ID)
    b = ArtifactDirectory.create(tmp_path / "b", RUN_ID)
    pa = write_score(a, run_id=RUN_ID, score=qs1, policy_decision=fixture_policy_decision_pass)
    pb = write_score(b, run_id=RUN_ID, score=qs2, policy_decision=fixture_policy_decision_pass)
    payload_a = json.loads(pa.read_text())
    payload_b = json.loads(pb.read_text())
    assert payload_a["total"] == payload_b["total"] == 0.3


def test_score_round_trip_reproducible(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    """Re-writing the same QualityScore must yield byte-identical output."""
    a = ArtifactDirectory.create(tmp_path / "a", RUN_ID)
    b = ArtifactDirectory.create(tmp_path / "b", RUN_ID)
    write_score(
        a,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
        policy_config=POLICY_CONFIG,
    )
    write_score(
        b,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
        policy_config=POLICY_CONFIG,
    )
    assert (a.path("score.json")).read_text() == (b.path("score.json")).read_text()
