"""Shared helpers that translate check verdicts into typed Findings.

Every per-check module returns a tuple of :class:`CheckFinding`
records — small intermediate structs that carry the rule ID, the
specific evidence, and any per-finding severity / confidence
overrides. ``findings_from_check_findings`` consolidates them into
the documentation / §20-compliant :class:`engine.domain.finding.Finding`
records ready for the lifecycle to persist.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence, EvidenceType
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.llm_audit.rules import LlmAuditRule, get_rule


@dataclass(frozen=True)
class CheckFinding:
    """Intermediate per-check result.

    Concrete checks return tuples of these; ``findings_from_check_findings``
    consolidates them into typed :class:`Finding` records. Keeping the
    intermediate type makes each check independently testable without
    pulling in the full Pydantic model surface.
    """

    rule_id: str
    title: str
    description: str
    route: str | None = None
    selector: str | None = None
    file: str | None = None
    line: int | None = None
    evidence_paths: tuple[str, ...] = field(default_factory=tuple)
    snippet: str | None = None
    severity_override: Severity | None = None
    confidence_override: float | None = None
    extra_context: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def findings_from_check_findings(
    check_findings: Iterable[CheckFinding],
    *,
    run_id: str,
    module_name: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_root: Path | None = None,
) -> tuple[Finding, ...]:
    """Translate :class:`CheckFinding` records into typed :class:`Finding`s.

    ``artifact_root`` is the run directory; the helper records the
    module's per-run artifact (``llm_audit/index.json``) as a fallback
    evidence reference when a check supplies none. The fallback
    satisfies our product spec's medium-or-above evidence requirement without
    pretending we captured a screenshot we don't have.
    """

    now = datetime.now(UTC)
    findings: list[Finding] = []
    for cf in check_findings:
        rule = get_rule(cf.rule_id)
        severity = cf.severity_override or rule.severity
        confidence = (
            cf.confidence_override if cf.confidence_override is not None else rule.confidence
        )
        evidence_paths = list(cf.evidence_paths)
        if not evidence_paths:
            evidence_paths.append("llm_audit/index.json")
        evidence_records = tuple(
            Evidence(
                id=id_generator.new("EVD"),
                type=_classify_evidence(path),
                path=Path(path),
            )
            for path in evidence_paths
        )
        description = cf.description.strip()
        if cf.snippet:
            snippet = cf.snippet.strip().replace("\r\n", "\n")
            if len(snippet) > 800:
                snippet = snippet[:800] + "…"
            description = f"{description}\n\nObserved:\n{snippet}"
        if cf.extra_context:
            ctx_block = "\n".join(f"- {key}: {value}" for key, value in cf.extra_context)
            description = f"{description}\n\nContext:\n{ctx_block}"
        if len(description) > 7800:
            description = description[:7800] + "…"
        findings.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module=module_name,
                category=rule.category,
                severity=severity,
                confidence=confidence,
                title=cf.title or rule.title,
                description=description,
                location=FindingLocation(
                    route=cf.route,
                    selector=cf.selector,
                    file=cf.file,
                    line=cf.line,
                ),
                evidence=evidence_records,
                reproduction_steps=(),
                suggested_fix=None,
                affected_target=target_base_url,
                recommendation=rule.remediation,
                created_at=now,
            )
        )
        # ``artifact_root`` is accepted for future-proofing the wire
        # format; the helper still uses Path-only evidence references.
        _ = artifact_root
    return tuple(findings)


def _classify_evidence(path: str) -> EvidenceType:
    lowered = path.lower()
    if lowered.endswith((".png", ".jpg", ".jpeg")):
        return "screenshot"
    if lowered.endswith((".webm", ".mp4")):
        return "video"
    if lowered.endswith(".zip"):
        return "trace"
    if lowered.endswith(".har"):
        return "har"
    if lowered.endswith((".log", ".txt")):
        return "console_log"
    if lowered.endswith(".html"):
        return "dom_snapshot"
    return "source_ref"


__all__ = [
    "CheckFinding",
    "LlmAuditRule",
    "findings_from_check_findings",
]
