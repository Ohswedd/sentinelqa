"""Every artifact-producing model carries schema_version."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.domain import (
    Finding,
    IdGenerator,
    PolicyDecision,
    QualityScore,
    RepairSuggestion,
    Target,
)
from engine.domain import TestRun as TestRunModel

GEN = IdGenerator()


def test_test_run_has_schema_version() -> None:
    run = TestRunModel(
        id=GEN.new("RUN"),
        started_at=datetime.now(UTC),
        target=Target(base_url="http://localhost:3000", allowed_hosts=["localhost"]),
    )
    payload = run.to_dict()
    assert payload["schema_version"] == "1"


def test_finding_has_schema_version() -> None:
    run_id = GEN.new("RUN")
    f = Finding(
        id=GEN.new("FND"),
        run_id=run_id,
        module="m",
        category="c",
        severity="info",
        confidence=0.5,
        title="t",
        description="d",
        created_at=datetime.now(UTC),
    )
    assert f.to_dict()["schema_version"] == "1"


def test_quality_score_has_schema_version() -> None:
    qs = QualityScore(id=GEN.new("SCR"), run_id=GEN.new("RUN"), total=85.0)
    assert qs.to_dict()["schema_version"] == "1"


def test_policy_decision_has_schema_version() -> None:
    pd = PolicyDecision(
        id=GEN.new("PD"),
        run_id=GEN.new("RUN"),
        release_decision="pass",
    )
    assert pd.to_dict()["schema_version"] == "1"


def test_repair_suggestion_has_schema_version() -> None:
    rs = RepairSuggestion(
        id=GEN.new("RPR"),
        target_test="tests/foo.spec.ts",
        original="a",
        proposed="b",
        confidence=0.9,
        reason="r",
    )
    assert rs.to_dict()["schema_version"] == "1"


def test_target_has_schema_version() -> None:
    t = Target(base_url="http://localhost:3000", allowed_hosts=["localhost"])
    assert t.to_dict()["schema_version"] == "1"


def test_target_proof_path_serializes_as_string() -> None:
    t = Target(
        base_url="http://localhost:3000",
        allowed_hosts=["localhost"],
        proof_of_authorization=Path("./.sentinel/proof.yaml"),
    )
    assert t.to_dict()["proof_of_authorization"].endswith("proof.yaml")
