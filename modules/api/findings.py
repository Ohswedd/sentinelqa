"""Translate :class:`ApiIssue` records into PRD §18.2 :class:`Finding`s."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.ids import IdGenerator

from modules.api.cwe_mapping import lookup as cwe_lookup
from modules.api.models import ApiCheckResult, ApiIssue


def _issue_to_finding(
    issue: ApiIssue,
    *,
    check: str,
    run_id: str,
    target_base_url: str,
    artifact_path: str,
    id_generator: IdGenerator,
    timestamp: datetime,
) -> Finding:
    location = FindingLocation(route=issue.route)
    evidence = (
        Evidence(
            id=id_generator.new("EVD"),
            type="api_sample",
            path=Path(artifact_path),
        ),
    )
    extras_text = "; ".join(f"{k}={v}" for k, v in sorted(issue.evidence.items()))
    body = issue.description
    if issue.method and issue.route:
        body = f"{issue.method} {issue.route}\n\n{body}"
    if issue.expected_status is not None and issue.observed_status is not None:
        body = (
            f"{body}\n\nExpected status: {issue.expected_status}; "
            f"observed: {issue.observed_status}."
        )
    if extras_text:
        body = f"{body}\n\nEvidence: {extras_text}"
    category = f"api/{check}/{issue.rule_id.lower()}"
    ids = cwe_lookup(category)
    return Finding(
        id=id_generator.new("FND"),
        run_id=run_id,
        module="api",
        category=category,
        severity=issue.severity,
        confidence=issue.confidence,
        title=issue.title,
        description=body,
        location=location,
        evidence=evidence,
        suggested_fix=issue.recommendation,
        affected_target=target_base_url,
        recommendation=issue.recommendation,
        cwe_id=ids.cwe_id,
        attack_id=ids.attack_id,
        owasp_api_id=ids.owasp_api_id,
        created_at=timestamp,
    )


def findings_from_checks(
    *,
    checks: Iterable[ApiCheckResult],
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_paths: dict[str, str] | None = None,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """Convert every issue in every check into a :class:`Finding`."""

    timestamp = now or datetime.now(UTC)
    artifact_paths = artifact_paths or {}
    out: list[Finding] = []
    for result in checks:
        artifact_path = artifact_paths.get(result.check, f"api/{result.check}.json")
        for issue in result.issues:
            out.append(
                _issue_to_finding(
                    issue,
                    check=result.check,
                    run_id=run_id,
                    target_base_url=target_base_url,
                    artifact_path=artifact_path,
                    id_generator=id_generator,
                    timestamp=timestamp,
                )
            )
    return tuple(out)


__all__ = ["findings_from_checks"]
