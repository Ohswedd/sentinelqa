"""Unit tests for :mod:`modules.accessibility.findings`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from engine.domain.ids import IdGenerator

from modules.accessibility.findings import (
    findings_from_page,
    findings_from_pages,
    short_rule_hash,
)
from modules.accessibility.models import (
    A11yPageResult,
    AccessibleNameIssue,
    AxeImpact,
    AxeNode,
    AxeViolation,
    KeyboardIssue,
    LandmarkIssue,
)


def _violation(
    rule_id: str,
    impact: AxeImpact = "serious",
    *,
    tags: tuple[str, ...] = ("wcag2aa",),
    target: str = "button.x",
) -> AxeViolation:
    return AxeViolation(
        rule_id=rule_id,
        impact=impact,
        help=f"{rule_id} help",
        help_url=f"https://example.test/{rule_id}",
        description=f"{rule_id} description",
        tags=tags,
        nodes=(AxeNode(target=(target,), html=f"<button class='{rule_id}'/>"),),
        experimental="experimental" in tags,
    )


def _page(*violations: AxeViolation) -> A11yPageResult:
    return A11yPageResult(
        route="/dashboard",
        url="http://localhost:3000/dashboard",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=tuple(violations),
        duration_ms=10,
    )


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "impact, expected",
    [
        ("critical", "high"),
        ("serious", "high"),
        ("moderate", "medium"),
        ("minor", "low"),
    ],
)
def test_axe_impact_severity_mapping(impact: AxeImpact, expected: str) -> None:
    findings = findings_from_page(
        page=_page(_violation("rule-x", impact)),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert findings[0].severity == expected


def test_experimental_rules_lower_confidence() -> None:
    findings = findings_from_page(
        page=_page(_violation("rule-x", "moderate", tags=("experimental",))),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert findings[0].confidence == pytest.approx(0.6)


def test_non_experimental_rules_high_confidence() -> None:
    findings = findings_from_page(
        page=_page(_violation("rule-x", "moderate")),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert findings[0].confidence == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# Wording guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phrase", ["fully WCAG", "WCAG compliant", "fully compliant"])
def test_findings_never_claim_wcag_compliance(phrase: str) -> None:
    page = A11yPageResult(
        route="/dashboard",
        url="http://localhost:3000/dashboard",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=(_violation("rule-x"),),
        keyboard_issues=(
            KeyboardIssue(
                category="focus-trap",
                selector=".modal",
                description="Tab cannot escape",
            ),
        ),
        landmark_issues=(
            LandmarkIssue(
                category="missing-landmark",
                landmark="main",
                description="No <main>",
            ),
        ),
        accessible_name_issues=(
            AccessibleNameIssue(
                selector="#icon",
                role="button",
                description="No accessible name",
            ),
        ),
        duration_ms=10,
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )
    for finding in findings:
        assert phrase not in finding.title, finding.title
        assert phrase not in finding.description, finding.description
        recommendation = finding.recommendation or ""
        assert phrase not in recommendation, recommendation


def test_titles_use_canonical_prefix() -> None:
    findings = findings_from_page(
        page=_page(_violation("rule-x")),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert findings[0].title.startswith("Automated accessibility check found")


# ---------------------------------------------------------------------------
# Evidence + metadata
# ---------------------------------------------------------------------------


def test_findings_attach_artifact_evidence_when_provided() -> None:
    findings = findings_from_pages(
        pages=(_page(_violation("rule-x")),),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        artifact_paths={"/dashboard": "a11y/dashboard.json"},
    )
    finding = findings[0]
    assert len(finding.evidence) == 1
    assert str(finding.evidence[0].path) == "a11y/dashboard.json"
    assert finding.evidence[0].type == "source_ref"


def test_findings_fall_back_to_runner_log_when_artifact_missing() -> None:
    findings = findings_from_pages(
        pages=(_page(_violation("rule-x")),),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        artifact_paths={},
    )
    finding = findings[0]
    assert len(finding.evidence) == 1
    assert str(finding.evidence[0].path) == "logs/runner.accessibility.log"


def test_finding_location_uses_target_selector() -> None:
    findings = findings_from_page(
        page=_page(_violation("rule-x", target="button#go")),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert findings[0].location.selector == "button#go"
    assert findings[0].location.route == "/dashboard"


def test_short_rule_hash_is_deterministic() -> None:
    h1 = short_rule_hash("color-contrast", "/", "div.x")
    h2 = short_rule_hash("color-contrast", "/", "div.x")
    h3 = short_rule_hash("color-contrast", "/", "div.y")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 8


def test_curated_remediation_applied() -> None:
    findings = findings_from_page(
        page=_page(_violation("color-contrast", "serious")),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert findings[0].recommendation is not None
    assert "4.5:1" in findings[0].recommendation


def test_uncurated_rule_falls_back_to_axe_help() -> None:
    findings = findings_from_page(
        page=_page(_violation("aria-allowed-attr", "serious")),
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    # The fixture sets help to "<rule-id> help".
    assert findings[0].recommendation == "aria-allowed-attr help"
