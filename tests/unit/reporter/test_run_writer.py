"""Unit tests for the ``run.json`` writer helpers (task 03.01)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.run_writer import (
    ARTIFACT_SLOTS,
    RUN_REPORT_SCHEMA_VERSION,
    build_run_report,
    canonical_config_digest,
    derive_release_decision,
    summarize_modules_and_findings,
    write_run,
)


def test_canonical_config_digest_is_deterministic() -> None:
    snapshot_a = {"b": 2, "a": [1, 2, 3]}
    snapshot_b = {"a": [1, 2, 3], "b": 2}
    assert canonical_config_digest(snapshot_a) == canonical_config_digest(snapshot_b)


def test_canonical_config_digest_format() -> None:
    digest = canonical_config_digest({"foo": "bar"})
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_canonical_config_digest_handles_paths_and_sets() -> None:
    d1 = canonical_config_digest({"path": Path("/tmp/a"), "hosts": {"a", "b"}})
    d2 = canonical_config_digest({"path": "/tmp/a", "hosts": ["a", "b"]})
    assert d1 == d2


def test_canonical_config_digest_differs_for_different_inputs() -> None:
    d1 = canonical_config_digest({"a": 1})
    d2 = canonical_config_digest({"a": 2})
    assert d1 != d2


@pytest.mark.parametrize(
    "status, expected",
    [
        ("unsafe_blocked", "unsafe_target_rejected"),
        ("dry_run", "inconclusive"),
        ("passed", "pass"),
        ("failed", "blocked"),
        ("incomplete", "inconclusive"),
    ],
)
def test_derive_release_decision_without_policy(status: str, expected: str) -> None:
    actual = derive_release_decision(run_status=status, policy=None)  # type: ignore[arg-type]
    assert actual == expected


def test_derive_release_decision_with_policy_is_authoritative() -> None:
    policy = PolicyDecision(
        id="PD-AUTHAAAAAAAA",
        run_id="RUN-AUTHAAAAAAAA",
        release_decision="pass_with_warnings",
        blocked_by=(),
        reasons=("Warning-only finding.",),
    )
    actual = derive_release_decision(run_status="passed", policy=policy)
    assert actual == "pass_with_warnings"


def test_summarize_modules_and_findings_counts_each_bucket() -> None:
    summary = summarize_modules_and_findings(module_results=(), findings=())
    assert summary == {"passed": 0, "failed": 0, "blocked": 0, "info": 0}


def test_build_run_report_unsafe_has_null_score(
    fixture_test_run_unsafe: TestRun,
) -> None:
    report = build_run_report(fixture_test_run_unsafe)
    assert report.quality_score is None
    assert report.release_decision == "unsafe_target_rejected"
    assert report.schema_version == RUN_REPORT_SCHEMA_VERSION
    assert tuple(report.artifact_paths.keys()) == ARTIFACT_SLOTS


def test_build_run_report_dry_run_has_null_score(
    fixture_test_run_dry: TestRun,
) -> None:
    report = build_run_report(fixture_test_run_dry)
    assert report.quality_score is None
    assert report.release_decision == "inconclusive"


def test_build_run_report_passed_rounds_quality_score(
    fixture_test_run_passed: TestRun,
) -> None:
    score = QualityScore(
        id="SCR-ROUNDAAAAAAA",
        run_id=fixture_test_run_passed.id,
        total=87.256789,
        components={},
        weights={},
        severity_penalties_applied={},
    )
    report = build_run_report(fixture_test_run_passed, score=score)
    assert report.quality_score == 87.26


def test_write_run_redacts_secrets_in_errors(tmp_path: Path) -> None:
    target = Target(base_url="https://localhost:8080", mode="safe")
    started = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
    run = TestRun(
        id="RUN-REDACTAAAAAB",
        started_at=started,
        finished_at=started,
        target=target,
        config_snapshot={"target": {"base_url": "https://localhost:8080"}},
        modules_run=(),
        status="failed",
    )
    artifacts = ArtifactDirectory.create(tmp_path, run.id)
    written = write_run(
        artifacts,
        run,
        config_snapshot=run.config_snapshot,
        errors=(
            {
                "code": "E-RUN-001",
                "message": "Authorization: Bearer sk-this-is-a-secret-token",
            },
        ),
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    msg = payload["errors"][0]["message"]
    assert "sk-this-is-a-secret-token" not in msg
    assert "REDACTED" in msg


def test_write_run_artifact_slot_defaults_to_null(tmp_path: Path) -> None:
    target = Target(base_url="https://localhost:8080", mode="safe")
    started = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
    run = TestRun(
        id="RUN-DEFAULTSAAAA",
        started_at=started,
        finished_at=None,
        target=target,
        config_snapshot={},
        modules_run=(),
        status="incomplete",
    )
    artifacts = ArtifactDirectory.create(tmp_path, run.id)
    written = write_run(artifacts, run)
    payload = json.loads(written.read_text(encoding="utf-8"))
    for slot in ARTIFACT_SLOTS:
        assert slot in payload["artifact_paths"]
        assert payload["artifact_paths"][slot] is None


def test_canonical_config_digest_handles_pydantic_model() -> None:
    """`canonical_config_digest` recurses into nested Pydantic models."""

    target = Target(base_url="https://localhost:8080", mode="safe")
    digest_via_model = canonical_config_digest({"target": target})
    digest_via_dict = canonical_config_digest({"target": target.to_dict()})
    assert digest_via_model == digest_via_dict


def test_canonical_config_digest_handles_frozenset() -> None:
    d1 = canonical_config_digest({"hosts": frozenset({"b", "a"})})
    d2 = canonical_config_digest({"hosts": ["a", "b"]})
    assert d1 == d2


def test_normalize_error_falls_back_to_internal_code(tmp_path: Path) -> None:
    """Missing/empty error code and message default to safe placeholders."""

    target = Target(base_url="https://localhost:8080", mode="safe")
    started = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
    run = TestRun(
        id="RUN-DEFAULTSAAAB",
        started_at=started,
        finished_at=started,
        target=target,
        config_snapshot={},
        modules_run=(),
        status="failed",
    )
    artifacts = ArtifactDirectory.create(tmp_path, run.id)
    written = write_run(artifacts, run, errors=({"code": "", "message": ""},))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["errors"][0]["code"] == "E-INT-001"
    assert payload["errors"][0]["message"] == "Unspecified error."
