"""Agent-message builders for the SDK (the documentation, our engineering rules).

Every public exception, every :class:`Finding`, every
:class:`RepairSuggestion`, and the top-level :class:`AuditResult` expose
a stable, redacted dict shape for round-tripping to and from LLM
agents. The shapes are versioned via
:data:`engine.domain.schema.AGENT_MESSAGE_SCHEMA_VERSION`.

These builders are deterministic — given the same input, they produce
the same dict (and the same NDJSON / JSONL bytes when serialised via
:func:`sentinelqa.agent.format`). Tests pin the shapes via golden files.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from engine.domain.finding import Finding
from engine.domain.repair_suggestion import RepairSuggestion
from engine.domain.schema import (
    AGENT_MESSAGE_SCHEMA_VERSION,
    FINDINGS_SCHEMA_VERSION,
    REPAIR_SUGGESTION_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from engine.policy.redaction import redact

if TYPE_CHECKING:
    from sentinelqa._models import AuditResult


def finding_to_agent_message(finding: Finding) -> dict[str, Any]:
    """Return the canonical agent-message dict for a :class:`Finding`.

    Shape::

    {
    "type": "finding",
    "schema_version": FINDINGS_SCHEMA_VERSION,
    "agent_message_schema_version": AGENT_MESSAGE_SCHEMA_VERSION,
    "id": "FND-...",
    "module": "functional",
    "category": "...",
    "severity": "high",
    "confidence": 0.95,
    "title": "...",
    "description": "...",
    "recommendation": "...",
    "evidence_paths": ["traces/...", "screenshots/..."],
    "location": {"route": "/login", "selector": null, "file": null, "line": null},
    }

    Secrets are redacted via :func:`engine.policy.redaction.redact` before
    return so the dict is safe to ship straight to an LLM.
    """

    location = finding.location
    payload: dict[str, Any] = {
        "type": "finding",
        "schema_version": FINDINGS_SCHEMA_VERSION,
        "agent_message_schema_version": AGENT_MESSAGE_SCHEMA_VERSION,
        "id": finding.id,
        "run_id": finding.run_id,
        "module": finding.module,
        "category": finding.category,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "title": finding.title,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "suggested_fix": finding.suggested_fix,
        "evidence_paths": [str(e.path) for e in finding.evidence],
        "location": {
            "route": location.route,
            "selector": location.selector,
            "file": location.file,
            "line": location.line,
        },
        "affected_target": finding.affected_target,
    }
    redacted = redact(payload)
    assert isinstance(redacted, dict)
    return redacted


def repair_suggestion_to_agent_message(
    suggestion: RepairSuggestion,
) -> dict[str, Any]:
    """Return the canonical agent-message dict for a :class:`RepairSuggestion`.

    Matches the our engineering rules proposal schema verbatim — every healer
    suggestion must surface ``original``, ``proposed``, ``confidence``,
    ``reason``, ``evidence``, and ``requires_human_review`` so reviewers
    can judge without rerunning the failing test.
    """

    payload: dict[str, Any] = {
        "type": "repair_suggestion",
        "schema_version": REPAIR_SUGGESTION_SCHEMA_VERSION,
        "agent_message_schema_version": AGENT_MESSAGE_SCHEMA_VERSION,
        "id": suggestion.id,
        "target_test": suggestion.target_test,
        "original": suggestion.original,
        "proposed": suggestion.proposed,
        "confidence": suggestion.confidence,
        "reason": suggestion.reason,
        "evidence_paths": [str(e.path) for e in suggestion.evidence],
        "requires_human_review": suggestion.requires_human_review,
    }
    redacted = redact(payload)
    assert isinstance(redacted, dict)
    return redacted


def audit_result_to_agent_messages(
    result: AuditResult,
) -> tuple[dict[str, Any], ...]:
    """Return the full agent-message stream for an :class:`AuditResult`.

    See :meth:`AuditResult.to_agent_messages` for the full order /
    semantics.
    """

    summary = {
        "type": "run_summary",
        "schema_version": RUN_SCHEMA_VERSION,
        "agent_message_schema_version": AGENT_MESSAGE_SCHEMA_VERSION,
        "run_id": result.run_id,
        "status": result.status,
        "release_decision": result.release_decision,
        "passed": result.passed,
        "quality_score": result.quality_score,
        "target_url": result.target_url,
        "modules_run": list(result.modules_run),
        "finding_counts": _count_by_severity(result.findings),
        "started_at": result.started_at.isoformat(),
        "finished_at": (result.finished_at.isoformat() if result.finished_at else None),
        "run_dir": str(result.run_dir),
    }
    finding_messages = tuple(finding_to_agent_message(f) for f in result.findings)

    blockers = result.blockers
    blocker_summary = {
        "type": "blocker_summary",
        "agent_message_schema_version": AGENT_MESSAGE_SCHEMA_VERSION,
        "run_id": result.run_id,
        "blocking_count": len(blockers),
        "blocking_ids": [f.id for f in blockers],
        "failing_count": len(result.failures),
        "failing_ids": [f.id for f in result.failures],
    }

    next_actions = {
        "type": "next_actions",
        "agent_message_schema_version": AGENT_MESSAGE_SCHEMA_VERSION,
        "run_id": result.run_id,
        "actions": _suggest_next_actions(result),
    }

    redacted_summary = redact(summary)
    redacted_blockers = redact(blocker_summary)
    redacted_next = redact(next_actions)
    assert isinstance(redacted_summary, dict)
    assert isinstance(redacted_blockers, dict)
    assert isinstance(redacted_next, dict)
    return (
        redacted_summary,
        *finding_messages,
        redacted_blockers,
        redacted_next,
    )


def _count_by_severity(findings: Iterable[Finding]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _suggest_next_actions(result: AuditResult) -> list[str]:
    """Deterministic next-action list — no LLM, just shape-based heuristics."""

    actions: list[str] = []
    if result.status == "unsafe_blocked":
        actions.append(
            "Add the target host to `target.allowed_hosts` only if you own or "
            "are authorized to test it (our product spec, our engineering rules)."
        )
        return actions
    if result.status == "dry_run":
        actions.append("Re-run without `--dry-run` to execute the planned modules.")
        return actions
    if result.blockers:
        actions.append(f"Resolve {len(result.blockers)} blocking finding(s) before retrying.")
    elif result.failures:
        actions.append(
            f"Investigate {len(result.failures)} high/critical finding(s) — "
            "they may be promoted to blockers by your policy gate."
        )
    if result.status == "incomplete":
        actions.append(
            "One or more modules errored mid-run — inspect "
            "`logs/runner.<module>.log` under the run directory."
        )
    if not actions:
        actions.append("No action required — run passed cleanly.")
    return actions


__all__ = [
    "AGENT_MESSAGE_SCHEMA_VERSION",
    "audit_result_to_agent_messages",
    "finding_to_agent_message",
    "repair_suggestion_to_agent_message",
]
