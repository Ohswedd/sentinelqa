"""Translate compliance sub-check reports into :class:`Finding` records."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.compliance.models import (
    CcpaCategory,
    CcpaCheckReport,
    GdprCategory,
    GdprCheckReport,
    Soc2Category,
    Soc2CheckReport,
    Wcag22CheckReport,
    Wcag22SignalCategory,
)

_GDPR_SEVERITY: dict[GdprCategory, Severity] = {
    "cookies-before-consent": "high",
    "asymmetric-consent": "medium",
    "consent-banner-missing": "medium",
}

_GDPR_RECOMMENDATION: dict[GdprCategory, str] = {
    "cookies-before-consent": (
        "Block all non-essential cookies until the user has accepted "
        "the consent banner. Most CMPs ship a server-side gate for this."
    ),
    "asymmetric-consent": (
        "Add a single-click Reject button next to Accept in the consent "
        "banner. EDPB Guidelines 03/2022 require symmetric reject UX."
    ),
    "consent-banner-missing": (
        "Add a consent banner with one-click Accept and Reject before "
        "setting any non-essential cookie. Document the legal basis "
        "(GDPR Art. 6)."
    ),
}

_CCPA_SEVERITY: dict[CcpaCategory, Severity] = {
    "do-not-sell-link-missing": "medium",
    "do-not-sell-link-opt-out-missing": "medium",
}

_CCPA_RECOMMENDATION: dict[CcpaCategory, str] = {
    "do-not-sell-link-missing": (
        "Add a clearly visible 'Do Not Sell or Share My Personal "
        "Information' (or 'Your Privacy Choices') link in the page "
        "footer. The link must be present on every page that processes "
        "California consumer data."
    ),
    "do-not-sell-link-opt-out-missing": (
        "Make the linked page expose a working opt-out form — a clear "
        "control the visitor can submit to opt out of sale / sharing. "
        "A privacy policy alone is not enough."
    ),
}

_SOC2_SEVERITY: dict[Soc2Category, Severity] = {
    "trail-missing": "high",
    "trail-not-jsonl": "medium",
    "trail-non-monotonic": "high",
    "trail-secret-leak": "high",
    "trail-missing-safety-decision": "medium",
    "trail-missing-module-event": "medium",
    "trail-missing-artifact-event": "medium",
    "trail-missing-llm-event": "medium",
    "trail-missing-vault-event": "medium",
}

_SOC2_RECOMMENDATION: dict[Soc2Category, str] = {
    "trail-missing": (
        "Ensure every SentinelQA run writes ``audit.log``. The Phase 02 "
        "RunLifecycle owns this guarantee; check the run lifecycle for "
        "a missed write step."
    ),
    "trail-not-jsonl": (
        "Every audit-log line must be a single JSON object. Inspect the "
        "log writer for newline-stripping or pretty-printing issues."
    ),
    "trail-non-monotonic": (
        "The audit log must be append-only with monotonically-increasing "
        "timestamps. Investigate the offending line — it may indicate a "
        "tampering attempt or a clock skew bug."
    ),
    "trail-secret-leak": (
        "Tighten the redaction layer (engine.policy.redaction). The "
        "audit-log writer must redact Authorization headers, Set-Cookie "
        "values, and high-entropy tokens before flushing."
    ),
    "trail-missing-safety-decision": (
        "Ensure the safety policy enforcer writes its decision to the " "audit log on every run."
    ),
    "trail-missing-module-event": (
        "Ensure every module the run loaded emits paired module_start / "
        "module_end events in the audit log."
    ),
    "trail-missing-artifact-event": (
        "Ensure every persisted artifact (run.json, findings.json, …) "
        "writes an ``artifact_written`` event to the audit log."
    ),
    "trail-missing-llm-event": (
        "When the run includes LLM calls, every call must emit a "
        "``llm_call`` audit-log entry with provider + cost_usd. See "
        "Phase 30.09 wiring."
    ),
    "trail-missing-vault-event": (
        "When the run uses the encrypted vault (Phase 31), every "
        "vault access must emit a ``vault_access`` audit-log entry."
    ),
}


def _evidence_for_signals_path(
    id_generator: IdGenerator,
    artifact_path: str,
) -> tuple[Evidence, ...]:
    return (
        Evidence(
            id=id_generator.new("EVD"),
            type="source_ref",
            path=Path(artifact_path),
        ),
    )


def findings_from_gdpr(
    report: GdprCheckReport,
    *,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []
    for issue in report.issues:
        severity = _GDPR_SEVERITY[issue.category]
        recommendation = _GDPR_RECOMMENDATION[issue.category]
        title = f"Automated GDPR check found: {issue.category} on {issue.route}"
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="compliance",
                category=f"compliance.gdpr.{issue.category}",
                severity=severity,
                confidence=0.9,
                title=title[:300],
                description=issue.description,
                location=FindingLocation(route=issue.route),
                evidence=_evidence_for_signals_path(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=recommendation,
                suggested_fix=f"gdpr:{issue.category}",
                compliance_id=issue.compliance_id,
                created_at=timestamp,
            )
        )
    return tuple(out)


def findings_from_ccpa(
    report: CcpaCheckReport,
    *,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []
    for issue in report.issues:
        severity = _CCPA_SEVERITY[issue.category]
        recommendation = _CCPA_RECOMMENDATION[issue.category]
        title = f"Automated CCPA check found: {issue.category} on {issue.route}"
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="compliance",
                category=f"compliance.ccpa.{issue.category}",
                severity=severity,
                confidence=0.9,
                title=title[:300],
                description=issue.description,
                location=FindingLocation(route=issue.route),
                evidence=_evidence_for_signals_path(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=recommendation,
                suggested_fix=f"ccpa:{issue.category}",
                compliance_id=issue.compliance_id,
                created_at=timestamp,
            )
        )
    return tuple(out)


def findings_from_soc2(
    report: Soc2CheckReport,
    *,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []
    for issue in report.issues:
        severity = _SOC2_SEVERITY[issue.category]
        recommendation = _SOC2_RECOMMENDATION[issue.category]
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="compliance",
                category=f"compliance.soc2.{issue.category}",
                severity=severity,
                confidence=0.95,
                title=(f"Automated SOC 2 trail check found: {issue.category}")[:300],
                description=issue.description,
                evidence=_evidence_for_signals_path(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=recommendation,
                suggested_fix=f"soc2:{issue.category}",
                compliance_id=issue.compliance_id,
                created_at=timestamp,
            )
        )
    return tuple(out)


_WCAG22_SEVERITY: dict[Wcag22SignalCategory, Severity] = {
    "focus-obscured": "medium",
    "target-size-min": "medium",
    "dragging-movements": "medium",
    "redundant-entry": "low",
    "accessible-authentication": "high",
}

_WCAG22_RECOMMENDATION: dict[Wcag22SignalCategory, str] = {
    "focus-obscured": (
        "Add ``scroll-padding-top`` matching the sticky overlay height "
        "so focused controls stay visible when focused."
    ),
    "target-size-min": (
        "Increase clickable targets to at least 24x24 CSS px, or rely "
        "on the SC 2.5.8 spacing exception (24 px clear margin)."
    ),
    "dragging-movements": (
        "Provide arrow-key, explicit move-buttons, or numeric inputs "
        "so the control is operable without drag gestures."
    ),
    "redundant-entry": (
        "Pre-fill the field from the prior step, or offer an explicit "
        '"same as previous" affordance.'
    ),
    "accessible-authentication": (
        "Offer an alternative authentication path (passkey, TOTP, "
        "hardware token, magic link) that does not require a "
        "cognitive function test."
    ),
}


def findings_from_wcag22(
    report: Wcag22CheckReport,
    *,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []
    for issue in report.issues:
        severity = _WCAG22_SEVERITY[issue.category]
        recommendation = _WCAG22_RECOMMENDATION[issue.category]
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="compliance",
                category=f"compliance.wcag-2.2.{issue.category}",
                severity=severity,
                confidence=0.9,
                title=(
                    f"Automated WCAG 2.2 check found (SC "
                    f"{issue.success_criterion}): {issue.category}"
                )[:300],
                description=issue.description,
                location=FindingLocation(
                    route=issue.route,
                    selector=issue.selector or None,
                ),
                evidence=_evidence_for_signals_path(id_generator, artifact_path),
                affected_target=target_base_url,
                recommendation=recommendation,
                suggested_fix=f"wcag-2.2:{issue.category}",
                compliance_id=issue.compliance_id,
                created_at=timestamp,
            )
        )
    return tuple(out)


def findings_from_reports(
    *,
    gdpr: GdprCheckReport | None,
    ccpa: CcpaCheckReport | None,
    soc2: Soc2CheckReport | None,
    wcag22: Wcag22CheckReport | None = None,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_paths: dict[str, str],
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """Translate every available compliance check into typed findings."""

    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []
    if gdpr is not None:
        out.extend(
            findings_from_gdpr(
                gdpr,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_paths.get("gdpr", "compliance/gdpr.json"),
                now=timestamp,
            )
        )
    if ccpa is not None:
        out.extend(
            findings_from_ccpa(
                ccpa,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_paths.get("ccpa", "compliance/ccpa.json"),
                now=timestamp,
            )
        )
    if soc2 is not None:
        out.extend(
            findings_from_soc2(
                soc2,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_paths.get("soc2", "compliance/soc2_trail.json"),
                now=timestamp,
            )
        )
    if wcag22 is not None:
        out.extend(
            findings_from_wcag22(
                wcag22,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_paths.get("wcag22", "compliance/wcag22.json"),
                now=timestamp,
            )
        )
    return tuple(out)


def _iter_categories(issues: Iterable[object], attr: str = "category") -> tuple[str, ...]:
    return tuple(getattr(issue, attr) for issue in issues)


__all__ = [
    "findings_from_ccpa",
    "findings_from_gdpr",
    "findings_from_reports",
    "findings_from_soc2",
    "findings_from_wcag22",
]
