"""Phase 34.01 — Wcag22Issue → Finding translation."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.accessibility.findings import findings_from_page
from modules.accessibility.models import A11yPageResult, Wcag22Issue


def _page(*issues: Wcag22Issue) -> A11yPageResult:
    return A11yPageResult(
        route="/",
        url="https://example.test/",
        fetched_at=datetime.now(UTC).isoformat(),
        duration_ms=12,
        wcag22_issues=tuple(issues),
    )


def test_target_size_finding_carries_compliance_id_and_severity() -> None:
    page = _page(
        Wcag22Issue(
            category="target-size-min",
            success_criterion="2.5.8",
            selector="button.icon",
            description="20x20 button.",
        )
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="https://example.test",
        id_generator=IdGenerator(),
        artifact_path="a11y/index.json",
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.module == "accessibility"
    assert f.category == "a11y.wcag-2.2.target-size-min"
    assert f.severity == "medium"
    assert f.compliance_id == "wcag-2.2:target-size-min"
    assert f.suggested_fix == "wcag-2.2:target-size-min"
    assert f.recommendation is not None
    assert "Increase the clickable target" in f.recommendation


def test_accessible_authentication_is_high_severity() -> None:
    page = _page(
        Wcag22Issue(
            category="accessible-authentication",
            success_criterion="3.3.8",
            selector="#captcha",
            description="captcha-only.",
        )
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="https://example.test",
        id_generator=IdGenerator(),
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "high"
    assert f.compliance_id == "wcag-2.2:accessible-authentication-min"


def test_redundant_entry_is_low_severity() -> None:
    page = _page(
        Wcag22Issue(
            category="redundant-entry",
            success_criterion="3.3.7",
            selector="#email-2",
            description="repeated.",
        )
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="https://example.test",
        id_generator=IdGenerator(),
    )
    assert findings[0].severity == "low"
    assert findings[0].compliance_id == "wcag-2.2:redundant-entry"


def test_finding_description_uses_phase34_wording() -> None:
    page = _page(
        Wcag22Issue(
            category="focus-obscured",
            success_criterion="2.4.11",
            selector="#email",
            description="overlaps sticky.",
        )
    )
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="https://example.test",
        id_generator=IdGenerator(),
    )
    assert "Automated accessibility check found" in findings[0].description
    # Never claim full compliance.
    assert "fully WCAG" not in findings[0].description
    assert "WCAG compliant" not in findings[0].description
