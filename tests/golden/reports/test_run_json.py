"""Golden tests for ``run.json``.

Each test builds a deterministic :class:`TestRun` (and supporting state),
serializes it through :func:`engine.reporter.run_writer.write_run`, and
compares the result byte-for-byte against a committed golden file. The
golden lock makes drift impossible — any deliberate change requires
`SENTINELQA_UPDATE_GOLDENS=1` (or ``make update-goldens``).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.run_writer import write_run

from tests.conftest import assert_matches_golden

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "shared-schema" / "run.schema.json"


@pytest.fixture
def run_schema() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return payload


def _write_and_read(
    tmp_path: Path,
    run: TestRun,
    **kwargs: object,
) -> str:
    artifacts = ArtifactDirectory.create(tmp_path, run.id)
    written = write_run(artifacts, run, **kwargs)  # type: ignore[arg-type]
    return written.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Golden tests for the three lifecycle states (passed, unsafe_blocked, dry_run)
# ---------------------------------------------------------------------------


def test_run_json_golden_passed(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    actual = _write_and_read(
        tmp_path,
        fixture_test_run_passed,
        config_snapshot=fixture_test_run_passed.config_snapshot,
        findings=fixture_findings_mixed,
        module_results=fixture_module_results_passing,
        score=fixture_quality_score_passing,
        policy=fixture_policy_decision_pass,
        artifact_paths={
            "findings": "findings.json",
            "score": "score.json",
            "junit": "junit.xml",
            "sarif": "sarif.json",
            "report_html": "report.html",
            "report_md": "report.md",
            "audit_log": "audit.log",
        },
    )
    assert_matches_golden(actual, goldens_root / "run.passed.golden.json")


def test_run_json_golden_unsafe(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_unsafe: TestRun,
) -> None:
    actual = _write_and_read(
        tmp_path,
        fixture_test_run_unsafe,
        config_snapshot=fixture_test_run_unsafe.config_snapshot,
        errors=(
            {
                "code": "E-SAFE-001",
                "message": "Host 'example.com' is not in target.allowed_hosts and is not local.",
            },
        ),
        artifact_paths={
            "findings": None,
            "score": None,
            "junit": None,
            "sarif": None,
            "report_html": None,
            "report_md": None,
            "audit_log": "audit.log",
        },
    )
    assert_matches_golden(actual, goldens_root / "run.unsafe.golden.json")


def test_run_json_golden_dry_run(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_dry: TestRun,
) -> None:
    actual = _write_and_read(
        tmp_path,
        fixture_test_run_dry,
        config_snapshot=fixture_test_run_dry.config_snapshot,
        artifact_paths={
            "findings": None,
            "score": None,
            "junit": None,
            "sarif": None,
            "report_html": None,
            "report_md": None,
            "audit_log": "audit.log",
        },
    )
    assert_matches_golden(actual, goldens_root / "run.dry_run.golden.json")


# ---------------------------------------------------------------------------
# Schema-validation: every golden must validate against run.schema.json.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "golden_name",
    ["run.passed.golden.json", "run.unsafe.golden.json", "run.dry_run.golden.json"],
)
def test_golden_validates_against_schema(
    goldens_root: Path,
    run_schema: dict[str, Any],
    golden_name: str,
) -> None:
    golden_path = goldens_root / golden_name
    if not golden_path.exists():
        pytest.skip(
            f"Golden {golden_name} not yet generated (run with SENTINELQA_UPDATE_GOLDENS=1)."
        )
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, run_schema)  # raises on failure


# ---------------------------------------------------------------------------
# write_run is idempotent for the same input.
# ---------------------------------------------------------------------------


def test_write_run_is_idempotent(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    path1 = write_run(
        artifacts,
        fixture_test_run_passed,
        config_snapshot=fixture_test_run_passed.config_snapshot,
        findings=fixture_findings_mixed,
        module_results=fixture_module_results_passing,
        score=fixture_quality_score_passing,
        policy=fixture_policy_decision_pass,
    )
    first = path1.read_text(encoding="utf-8")
    path2 = write_run(
        artifacts,
        fixture_test_run_passed,
        config_snapshot=fixture_test_run_passed.config_snapshot,
        findings=fixture_findings_mixed,
        module_results=fixture_module_results_passing,
        score=fixture_quality_score_passing,
        policy=fixture_policy_decision_pass,
    )
    second = path2.read_text(encoding="utf-8")
    assert first == second, "write_run must be byte-identical for the same input."


# ---------------------------------------------------------------------------
# Sanity check on RFC 3339 + canonical timestamps.
# ---------------------------------------------------------------------------


def test_started_at_round_trips_rfc3339(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
    fixture_started_at: datetime,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_run(
        artifacts,
        fixture_test_run_passed,
        config_snapshot=fixture_test_run_passed.config_snapshot,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["started_at"] == fixture_started_at.isoformat()
    # Parse back round-trips
    parsed = datetime.fromisoformat(payload["started_at"])
    assert parsed == fixture_started_at
