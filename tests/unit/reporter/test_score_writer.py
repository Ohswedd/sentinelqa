"""Unit tests for the ``score.json`` writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.score_writer import (
    COMPONENT_AXES,
    DEFAULT_POLICY,
    SCORE_REPORT_SCHEMA_VERSION,
    SEVERITY_BUCKETS,
    write_score,
)

RUN_ID = "RUN-SCORETESTAAA"


def test_write_score_passing(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCORE_REPORT_SCHEMA_VERSION
    assert payload["total"] == 87.25
    assert payload["release_decision"] == "pass"
    assert payload["blockers"] == []
    # All axes are present even when unset.
    for axis in COMPONENT_AXES:
        assert axis in payload["components"]
        assert axis in payload["weights"]
    for bucket in SEVERITY_BUCKETS:
        assert bucket in payload["severity_penalties"]


def test_write_score_unset_axes_default_to_zero(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    # The fixture only sets functional/accessibility/performance/security.
    assert payload["components"]["api"] == 0.0
    assert payload["components"]["visual"] == 0.0


def test_write_score_total_is_rounded(
    tmp_path: Path,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    qs = QualityScore(
        id="SCR-ROUNDAAAAAAA",
        run_id=RUN_ID,
        total=87.256789,
        components={},
        weights={},
        severity_penalties_applied={},
    )
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=qs,
        policy_decision=fixture_policy_decision_pass,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["total"] == 87.26


def test_write_score_none_yields_null_total(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=None,
        policy_decision=None,
        release_decision="unsafe_target_rejected",
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["total"] is None
    assert payload["release_decision"] == "unsafe_target_rejected"
    assert payload["components"]["functional"] == 0.0


def test_write_score_policy_defaults_applied(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    for key, default in DEFAULT_POLICY.items():
        assert payload["policy"][key] == default


def test_write_score_policy_override_partial(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
        policy_config={"min_quality_score": 90, "max_flake_rate": 0.01},
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["policy"]["min_quality_score"] == 90.0
    assert payload["policy"]["max_flake_rate"] == 0.01
    # Other defaults preserved.
    assert payload["policy"]["block_on_critical"] is True


def test_write_score_is_idempotent(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    p1 = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
    )
    p2 = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
    )
    assert p1.read_text() == p2.read_text()


@pytest.mark.parametrize(
    "raw, expected",
    [(80, 80.0), (80.0, 80.0), ("90", 90.0)],
)
def test_policy_min_quality_score_coerced_to_float(
    tmp_path: Path,
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
    raw: object,
    expected: float,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_score(
        artifacts,
        run_id=RUN_ID,
        score=fixture_quality_score_passing,
        policy_decision=fixture_policy_decision_pass,
        policy_config={"min_quality_score": raw},
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["policy"]["min_quality_score"] == expected
