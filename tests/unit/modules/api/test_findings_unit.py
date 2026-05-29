"""Unit coverage for the findings translator."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.api.findings import findings_from_checks
from modules.api.models import API_RESULT_SCHEMA_VERSION, ApiCheckResult, ApiIssue


def _result(*issues: ApiIssue) -> ApiCheckResult:
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="contract",
        issues=tuple(issues),
        targets_scanned=len(issues),
        duration_ms=1,
    )


def test_finding_includes_method_and_route_when_both_present() -> None:
    issue = ApiIssue(
        rule_id="X",
        severity="medium",
        confidence=0.5,
        title="t",
        description="body",
        method="GET",
        route="/x",
        recommendation="r",
    )
    findings = findings_from_checks(
        checks=(_result(issue),),
        run_id="RUN-FINDINGSTEST",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    assert "GET /x" in findings[0].description


def test_finding_omits_route_prefix_when_method_missing() -> None:
    issue = ApiIssue(
        rule_id="X",
        severity="medium",
        confidence=0.5,
        title="t",
        description="body",
        method=None,
        route="/x",
        recommendation="r",
    )
    findings = findings_from_checks(
        checks=(_result(issue),),
        run_id="RUN-FINDINGSTEST",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    assert "GET /x" not in findings[0].description


def test_finding_uses_now_argument_when_supplied() -> None:
    issue = ApiIssue(
        rule_id="X",
        severity="info",
        confidence=0.5,
        title="t",
        description="body",
        recommendation="r",
    )
    pinned = datetime(2026, 1, 1, tzinfo=UTC)
    findings = findings_from_checks(
        checks=(_result(issue),),
        run_id="RUN-FINDINGSTEST",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        now=pinned,
    )
    assert findings[0].created_at == pinned


def test_finding_uses_artifact_path_overrides() -> None:
    issue = ApiIssue(
        rule_id="X",
        severity="info",
        confidence=0.5,
        title="t",
        description="body",
        recommendation="r",
    )
    findings = findings_from_checks(
        checks=(_result(issue),),
        run_id="RUN-FINDINGSTEST",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        artifact_paths={"contract": "custom/path.json"},
    )
    assert str(findings[0].evidence[0].path) == "custom/path.json"
