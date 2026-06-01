"""Translate :class:`A11yPageResult` into typed :class:`Finding` records.

CLAUDE §28 is the load-bearing rule: the module's text must never make
a full-WCAG-compliance claim. Outputs say "Automated accessibility
check found: <detail>". The forbidden-phrase guard in
``tests/security/test_no_wcag_compliance_claims.py`` enforces this.

The axe-impact → severity mapping follows the task file (11.05):

 critical → high serious → high moderate → medium minor → low

Confidence reflects how sound the underlying check is:

- axe rules tagged ``experimental`` → 0.6
- axe rules otherwise → 0.95
- keyboard / landmark / sr-name checks → 0.9

Curated remediations live in ``_AXE_REMEDIATIONS``; rules not in the
dictionary fall back to the rule's ``help`` text from axe-core.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.accessibility.models import (
    A11yPageResult,
    AccessibleNameIssue,
    AxeImpact,
    AxeViolation,
    KeyboardIssue,
    LandmarkIssue,
    Wcag22Category,
)

# ---------------------------------------------------------------------------
# Severity / confidence policy
# ---------------------------------------------------------------------------

_IMPACT_TO_SEVERITY: dict[AxeImpact, Severity] = {
    "critical": "high",
    "serious": "high",
    "moderate": "medium",
    "minor": "low",
}

_KEYBOARD_SEVERITY: dict[str, Severity] = {
    "focus-trap": "high",
    "keyboard-navigation": "medium",
    "focus-visible": "medium",
}

_LANDMARK_SEVERITY: dict[str, Severity] = {
    "missing-landmark": "medium",
    "duplicate-landmark": "low",
}

_WCAG22_SEVERITY: dict[Wcag22Category, Severity] = {
    "focus-obscured": "medium",
    "target-size-min": "medium",
    "dragging-movements": "medium",
    "redundant-entry": "low",
    "accessible-authentication": "high",
}

_WCAG22_COMPLIANCE_ID: dict[Wcag22Category, str] = {
    "focus-obscured": "wcag-2.2:focus-not-obscured-min",
    "target-size-min": "wcag-2.2:target-size-min",
    "dragging-movements": "wcag-2.2:dragging-movements",
    "redundant-entry": "wcag-2.2:redundant-entry",
    "accessible-authentication": "wcag-2.2:accessible-authentication-min",
}

_WCAG22_RECOMMENDATION: dict[Wcag22Category, str] = {
    "focus-obscured": (
        "Adjust the sticky / fixed element so the focused control "
        "remains at least partially visible when focused — typically "
        "by adding ``scroll-padding-top`` matching the overlay height."
    ),
    "target-size-min": (
        "Increase the clickable target to at least 24x24 CSS px, or "
        "ensure 24 px of clear space around it (the SC 2.5.8 spacing "
        "exception)."
    ),
    "dragging-movements": (
        "Provide a single-pointer alternative — arrow-key support, "
        "explicit move buttons, or a numeric position input — so the "
        "control is operable without drag gestures."
    ),
    "redundant-entry": (
        "Pre-fill the field from the prior step, or offer an explicit "
        '"same as previous" affordance.'
    ),
    "accessible-authentication": (
        "Offer an alternative authentication path that does not require "
        "a cognitive function test — passkeys, TOTP, hardware tokens, "
        "or magic links."
    ),
}

_AUTO_PREFIX = "Automated accessibility check found"

# Curated remediation strings. Keep them short and actionable.
_AXE_REMEDIATIONS: dict[str, str] = {
    "color-contrast": (
        "Increase the foreground/background contrast ratio to at least "
        "4.5:1 for normal text or 3:1 for large text."
    ),
    "image-alt": (
        "Add a descriptive ``alt`` attribute to the image, or set ``alt=''`` "
        "if the image is decorative."
    ),
    "button-name": (
        "Provide an accessible name via visible text, ``aria-label``, or "
        "``aria-labelledby`` on the button."
    ),
    "link-name": (
        "Provide visible link text or an ``aria-label`` so the link's "
        "purpose is clear when read aloud."
    ),
    "label": (
        "Associate the form control with a ``<label>`` (via ``for``/``id``) "
        "or use ``aria-labelledby``."
    ),
    "html-has-lang": (
        'Add a ``lang`` attribute (e.g. ``<html lang="en">``) so screen '
        "readers pick the correct pronunciation."
    ),
    "document-title": "Set a non-empty ``<title>`` element describing the page.",
    "region": (
        "Wrap top-level content in semantic landmarks (``<header>``, "
        "``<nav>``, ``<main>``, ``<footer>``) or ARIA roles."
    ),
    "landmark-one-main": "Ensure exactly one ``<main>`` or ``role='main'`` exists on the page.",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def findings_from_page(
    *,
    page: A11yPageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None = None,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """Translate one :class:`A11yPageResult` into a tuple of findings."""

    timestamp = now or datetime.now(UTC)
    findings: list[Finding] = []
    findings.extend(
        _axe_findings(
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    findings.extend(
        _keyboard_findings(
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    findings.extend(
        _landmark_findings(
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    findings.extend(
        _accessible_name_findings(
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    findings.extend(
        _wcag22_findings(
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    return tuple(findings)


def findings_from_pages(
    *,
    pages: Iterable[A11yPageResult],
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_paths: dict[str, str] | None = None,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """Translate every :class:`A11yPageResult` into a flat tuple of findings."""

    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []
    artifact_paths = artifact_paths or {}
    for page in pages:
        out.extend(
            findings_from_page(
                page=page,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_paths.get(page.route),
                now=timestamp,
            )
        )
    return tuple(out)


def short_rule_hash(rule_id: str, route: str, selector: str) -> str:
    """Stable short hash used in finding titles for grouping (the documentation)."""

    digest = hashlib.sha1(
        f"{rule_id}|{route}|{selector}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    return digest[:8]


# ---------------------------------------------------------------------------
# Per-check translators
# ---------------------------------------------------------------------------


def _axe_findings(
    *,
    page: A11yPageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for violation in page.axe_violations:
        severity = _IMPACT_TO_SEVERITY[violation.impact]
        confidence = 0.6 if violation.experimental else 0.95
        target_selector = (
            violation.nodes[0].target[0] if violation.nodes and violation.nodes[0].target else ""
        )
        short = short_rule_hash(violation.rule_id, page.route, target_selector)
        title = _truncate_for_title(
            f"{_AUTO_PREFIX}: {violation.help or violation.rule_id} " f"({violation.rule_id})"
        )
        description = _build_axe_description(violation, page=page)
        evidence = _build_evidence(
            page=page,
            id_generator=id_generator,
            artifact_path=artifact_path,
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="accessibility",
                category=f"a11y.{violation.rule_id}",
                severity=severity,
                confidence=confidence,
                title=title,
                description=description,
                location=FindingLocation(
                    route=page.route,
                    selector=target_selector or None,
                ),
                evidence=evidence,
                reproduction_steps=(
                    f"Load {page.url} in a desktop browser.",
                    f"Inspect the element {target_selector!r}.",
                    "Run the page through axe-core with the same axe tags.",
                ),
                affected_target=target_base_url,
                recommendation=_AXE_REMEDIATIONS.get(violation.rule_id, violation.help),
                suggested_fix=f"axe rule {violation.rule_id} (#{short})",
                created_at=timestamp,
            )
        )
    return out


def _keyboard_findings(
    *,
    page: A11yPageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for issue in page.keyboard_issues:
        severity = _KEYBOARD_SEVERITY[issue.category]
        title = _truncate_for_title(f"{_AUTO_PREFIX}: {issue.description} ({issue.category})")
        description = _build_keyboard_description(issue, page=page)
        evidence = _build_evidence(
            page=page,
            id_generator=id_generator,
            artifact_path=artifact_path,
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="accessibility",
                category=f"a11y.{issue.category}",
                severity=severity,
                confidence=0.9,
                title=title,
                description=description,
                location=FindingLocation(
                    route=page.route,
                    selector=issue.selector or None,
                ),
                evidence=evidence,
                reproduction_steps=(
                    f"Load {page.url}.",
                    "Tab through the page using only the keyboard.",
                    f"Observe the issue near {issue.selector or '<page>'}.",
                ),
                affected_target=target_base_url,
                recommendation=_keyboard_recommendation(issue),
                suggested_fix=f"keyboard:{issue.category}",
                created_at=timestamp,
            )
        )
    return out


def _landmark_findings(
    *,
    page: A11yPageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for issue in page.landmark_issues:
        severity = _LANDMARK_SEVERITY[issue.category]
        title = _truncate_for_title(
            f"{_AUTO_PREFIX}: {issue.description} ({issue.category}: {issue.landmark})"
        )
        description = _build_landmark_description(issue, page=page)
        evidence = _build_evidence(
            page=page,
            id_generator=id_generator,
            artifact_path=artifact_path,
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="accessibility",
                category=f"a11y.{issue.category}",
                severity=severity,
                confidence=0.9,
                title=title,
                description=description,
                location=FindingLocation(route=page.route),
                evidence=evidence,
                reproduction_steps=(
                    f"Load {page.url}.",
                    f"Inspect the landmark {issue.landmark!r} on the page.",
                ),
                affected_target=target_base_url,
                recommendation=_landmark_recommendation(issue),
                suggested_fix=f"landmark:{issue.category}:{issue.landmark}",
                created_at=timestamp,
            )
        )
    return out


def _accessible_name_findings(
    *,
    page: A11yPageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for issue in page.accessible_name_issues:
        title = _truncate_for_title(
            f"{_AUTO_PREFIX}: {issue.description} ({issue.role or 'interactive'})"
        )
        description = _build_accessible_name_description(issue, page=page)
        evidence = _build_evidence(
            page=page,
            id_generator=id_generator,
            artifact_path=artifact_path,
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="accessibility",
                category="a11y.accessible-name",
                severity="medium",
                confidence=0.9,
                title=title,
                description=description,
                location=FindingLocation(
                    route=page.route,
                    selector=issue.selector,
                ),
                evidence=evidence,
                reproduction_steps=(
                    f"Load {page.url}.",
                    f"Inspect the element {issue.selector!r} with the screen-reader name tool.",
                ),
                affected_target=target_base_url,
                recommendation=(
                    "Add visible text content, an ``aria-label``, or "
                    "``aria-labelledby`` so the element has a non-empty "
                    "accessible name."
                ),
                suggested_fix="accessible-name",
                created_at=timestamp,
            )
        )
    return out


def _wcag22_findings(
    *,
    page: A11yPageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for issue in page.wcag22_issues:
        severity = _WCAG22_SEVERITY[issue.category]
        compliance_id = _WCAG22_COMPLIANCE_ID[issue.category]
        recommendation = _WCAG22_RECOMMENDATION[issue.category]
        title = _truncate_for_title(
            f"{_AUTO_PREFIX} (WCAG 2.2 SC {issue.success_criterion}): " f"{issue.category}"
        )
        description = _truncate_for_description(
            f"{_AUTO_PREFIX} a WCAG 2.2 issue ({issue.category}) on "
            f"route {page.route!r}: {issue.description}"
        )
        evidence = _build_evidence(
            page=page,
            id_generator=id_generator,
            artifact_path=artifact_path,
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="accessibility",
                category=f"a11y.wcag-2.2.{issue.category}",
                severity=severity,
                confidence=0.9,
                title=title,
                description=description,
                location=FindingLocation(
                    route=page.route,
                    selector=issue.selector or None,
                ),
                evidence=evidence,
                reproduction_steps=(
                    f"Load {page.url}.",
                    (
                        f"Inspect {issue.selector!r}."
                        if issue.selector
                        else "Inspect the page structure."
                    ),
                ),
                affected_target=target_base_url,
                recommendation=recommendation,
                suggested_fix=f"wcag-2.2:{issue.category}",
                compliance_id=compliance_id,
                created_at=timestamp,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_for_title(text: str, *, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _build_axe_description(violation: AxeViolation, *, page: A11yPageResult) -> str:
    node_count = len(violation.nodes)
    tags = ", ".join(violation.tags) if violation.tags else "(no tags)"
    help_text = violation.help or "(no help text from axe-core)"
    detail = (
        f"{_AUTO_PREFIX} a {violation.impact} {violation.rule_id} violation on "
        f"route {page.route!r}. axe-core help: {help_text}. "
        f"Affected nodes: {node_count}. Rule tags: {tags}."
    )
    if violation.help_url:
        detail += f" Reference: {violation.help_url}."
    return _truncate_for_description(detail)


def _build_keyboard_description(issue: KeyboardIssue, *, page: A11yPageResult) -> str:
    return _truncate_for_description(
        f"{_AUTO_PREFIX} a keyboard accessibility issue ({issue.category}) on "
        f"route {page.route!r}: {issue.description}."
    )


def _build_landmark_description(issue: LandmarkIssue, *, page: A11yPageResult) -> str:
    return _truncate_for_description(
        f"{_AUTO_PREFIX} a landmark structure issue ({issue.category}) on "
        f"route {page.route!r}: {issue.description}."
    )


def _build_accessible_name_description(issue: AccessibleNameIssue, *, page: A11yPageResult) -> str:
    return _truncate_for_description(
        f"{_AUTO_PREFIX} a missing accessible name on route {page.route!r}: "
        f"{issue.description}."
    )


def _truncate_for_description(text: str, *, limit: int = 4_000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _keyboard_recommendation(issue: KeyboardIssue) -> str:
    if issue.category == "focus-trap":
        return (
            "Ensure focus can leave the modal via the Escape key or by "
            "tabbing past the last focusable element back to the page."
        )
    if issue.category == "focus-visible":
        return (
            "Provide a visible focus indicator (CSS ``:focus-visible``) for "
            "every focusable element."
        )
    return (
        "Make every interactive element reachable via the keyboard and "
        "ensure the tab order matches the visual reading order."
    )


def _landmark_recommendation(issue: LandmarkIssue) -> str:
    if issue.category == "missing-landmark":
        return (
            f"Add a ``<{issue.landmark}>`` element (or its ARIA equivalent) "
            "to the page structure."
        )
    return f"Ensure exactly one ``<{issue.landmark}>`` element exists on the page."


def _build_evidence(
    *,
    page: A11yPageResult,
    id_generator: IdGenerator,
    artifact_path: str | None,
) -> tuple[Evidence, ...]:
    """Always attach at least one evidence record.

    When the runner persisted a per-route JSON artifact, point at it.
    Otherwise fall back to ``logs/runner.accessibility.log``.
    """

    from pathlib import Path

    if artifact_path:
        return (
            Evidence(
                id=id_generator.new("EVD"),
                type="source_ref",
                path=Path(artifact_path),
            ),
        )
    return (
        Evidence(
            id=id_generator.new("EVD"),
            type="console_log",
            path=Path("logs/runner.accessibility.log"),
        ),
    )


__all__ = [
    "findings_from_page",
    "findings_from_pages",
    "short_rule_hash",
]
