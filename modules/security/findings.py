"""Translate :class:`SecurityIssue` records to the documentation :class:`Finding`s.

The module orchestrator emits one :class:`Finding` per issue. Evidence
on the finding points at the per-run artifact file
(``security/<check>.json``) so the Reporter renders a
recoverable link.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.ids import IdGenerator

from modules.security.cwe_mapping import lookup as cwe_lookup
from modules.security.models import SecurityCheckResult, SecurityIssue


def _issue_to_finding(
    issue: SecurityIssue,
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
    if extras_text:
        body = f"{body}\n\nEvidence: {extras_text}"
    category = f"security/{check}/{issue.rule_id.lower()}"
    ids = cwe_lookup(category)
    evidence_cwe = issue.evidence.get("cwe_id") if isinstance(issue.evidence, dict) else None
    evidence_attack = issue.evidence.get("attack_id") if isinstance(issue.evidence, dict) else None
    evidence_owasp = (
        issue.evidence.get("owasp_api_id") if isinstance(issue.evidence, dict) else None
    )
    return Finding(
        id=id_generator.new("FND"),
        run_id=run_id,
        module="security",
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
        cwe_id=str(evidence_cwe) if evidence_cwe is not None else ids.cwe_id,
        attack_id=str(evidence_attack) if evidence_attack is not None else ids.attack_id,
        owasp_api_id=str(evidence_owasp) if evidence_owasp is not None else ids.owasp_api_id,
        created_at=timestamp,
    )


def findings_from_checks(
    *,
    checks: Iterable[SecurityCheckResult],
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
        artifact_path = artifact_paths.get(result.check, f"security/{result.check}.json")
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
