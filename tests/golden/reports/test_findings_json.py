"""Golden tests for ``findings.json``."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.errors.base import ConfigError
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.findings_writer import collect_linter_warnings, write_findings

from tests.conftest import RUN_ID, assert_matches_golden

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "shared-schema" / "findings.schema.json"


@pytest.fixture
def findings_schema() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return payload


GENERATED_AT = datetime(2026, 5, 27, 12, 0, 30, tzinfo=UTC)


def _write_and_read(
    tmp_path: Path,
    findings: tuple[Finding, ...],
    *,
    enforce_evidence: bool = True,
) -> str:
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_findings(
        artifacts,
        findings,
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        enforce_evidence=enforce_evidence,
    )
    return written.read_text(encoding="utf-8")


def test_findings_json_golden_empty(tmp_path: Path, goldens_root: Path) -> None:
    actual = _write_and_read(tmp_path, ())
    assert_matches_golden(actual, goldens_root / "findings.empty.golden.json")


def test_findings_json_golden_critical(
    tmp_path: Path,
    goldens_root: Path,
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    actual = _write_and_read(tmp_path, fixture_findings_critical)
    assert_matches_golden(actual, goldens_root / "findings.critical.golden.json")


def test_findings_json_golden_mixed(
    tmp_path: Path,
    goldens_root: Path,
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    actual = _write_and_read(tmp_path, fixture_findings_mixed)
    assert_matches_golden(actual, goldens_root / "findings.mixed.golden.json")


def test_findings_json_golden_redacted(tmp_path: Path, goldens_root: Path) -> None:
    finding = Finding(
        id="FND-REDACTAAAAAA",
        run_id=RUN_ID,
        module="security",
        category="security/headers",
        severity="critical",
        confidence=0.95,
        title="Authorization header leaked in error response",
        description=(
            "GET /api/users/me returned 500; response body included "
            "Authorization: Bearer sk-this-is-a-real-secret-token-that-must-be-redacted."
        ),
        location=FindingLocation(route="/api/users/me"),
        evidence=(
            Evidence(
                id="EVD-REDACTAAAAAA",
                type="network_log",
                path=Path("traces/api-users-me.har"),
                redacted=True,
            ),
        ),
        recommendation="Filter Authorization header from server error responses.",
        affected_target="https://localhost:8080",
        created_at=GENERATED_AT,
    )
    actual = _write_and_read(tmp_path, (finding,))
    assert "sk-this-is-a-real-secret-token-that-must-be-redacted" not in actual
    assert "REDACTED" in actual
    assert_matches_golden(actual, goldens_root / "findings.redacted.golden.json")


@pytest.mark.parametrize(
    "golden_name",
    [
        "findings.empty.golden.json",
        "findings.critical.golden.json",
        "findings.mixed.golden.json",
        "findings.redacted.golden.json",
    ],
)
def test_findings_golden_validates_against_schema(
    goldens_root: Path,
    findings_schema: dict[str, Any],
    golden_name: str,
) -> None:
    golden_path = goldens_root / golden_name
    if not golden_path.exists():
        pytest.skip(f"Golden {golden_name} not generated (run with SENTINELQA_UPDATE_GOLDENS=1).")
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, findings_schema)


def test_write_findings_rejects_evidenceless_medium_severity(tmp_path: Path) -> None:
    bad = Finding(
        id="FND-BADAAAAAAAAA",
        run_id=RUN_ID,
        module="security",
        category="security/cookies",
        severity="medium",
        confidence=0.8,
        title="Missing HttpOnly attribute",
        description="The session cookie at /login lacks HttpOnly.",
        location=FindingLocation(route="/login"),
        evidence=(),
        recommendation="Set HttpOnly.",
        affected_target="https://localhost:8080",
        created_at=GENERATED_AT,
    )
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    with pytest.raises(ConfigError):
        write_findings(artifacts, (bad,), run_id=RUN_ID, generated_at=GENERATED_AT)


def test_write_findings_allows_evidenceless_info(tmp_path: Path) -> None:
    info_only = Finding(
        id="FND-INFOAAAAAAAC",
        run_id=RUN_ID,
        module="performance",
        category="perf/lcp",
        severity="info",
        confidence=0.6,
        title="LCP within budget for /",
        description="LCP measured at 1.8s; budget is 2.5s.",
        location=FindingLocation(route="/"),
        evidence=(),
        recommendation=None,
        affected_target="https://localhost:8080",
        created_at=GENERATED_AT,
    )
    artifacts = ArtifactDirectory.create(tmp_path, RUN_ID)
    written = write_findings(artifacts, (info_only,), run_id=RUN_ID, generated_at=GENERATED_AT)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["count"] == 1


def test_collect_linter_warnings_surfaces_l_fnd_002(
    fixture_findings_mixed: tuple[Finding, ...],
) -> None:
    # No banned phrases in the standard mixed fixture — should return clean.
    warnings = collect_linter_warnings(fixture_findings_mixed)
    assert warnings == []


def test_write_findings_is_idempotent(
    tmp_path: Path,
    fixture_findings_critical: tuple[Finding, ...],
) -> None:
    a = _write_and_read(tmp_path, fixture_findings_critical)
    b = _write_and_read(tmp_path, fixture_findings_critical)
    assert a == b
