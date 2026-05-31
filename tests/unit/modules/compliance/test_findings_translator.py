"""Phase 34 — compliance check → Finding translation edge cases."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.compliance.findings import (
    findings_from_ccpa,
    findings_from_gdpr,
    findings_from_reports,
    findings_from_soc2,
    findings_from_wcag22,
)
from modules.compliance.models import (
    CcpaCheckReport,
    CcpaIssue,
    GdprCheckReport,
    GdprIssue,
    Soc2CheckReport,
    Soc2Issue,
    Wcag22CheckReport,
    Wcag22Issue,
)


def _gen() -> IdGenerator:
    return IdGenerator()


def test_findings_from_gdpr_emits_compliance_id_and_high_severity() -> None:
    report = GdprCheckReport(
        pages_checked=1,
        issues=(
            GdprIssue(
                category="cookies-before-consent",
                route="/",
                description="cookie _ga before consent.",
                cookie_name="_ga",
                compliance_id="gdpr:Art.6",
            ),
        ),
    )
    findings = findings_from_gdpr(
        report,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_path="compliance/gdpr.json",
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "high"
    assert f.module == "compliance"
    assert f.compliance_id == "gdpr:Art.6"
    assert f.suggested_fix == "gdpr:cookies-before-consent"


def test_findings_from_ccpa_emits_medium_severity() -> None:
    report = CcpaCheckReport(
        pages_checked=1,
        issues=(
            CcpaIssue(
                category="do-not-sell-link-missing",
                route="/",
                description="missing link.",
                compliance_id="ccpa:do-not-sell-link",
            ),
        ),
    )
    findings = findings_from_ccpa(
        report,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_path="compliance/ccpa.json",
    )
    assert findings[0].severity == "medium"
    assert findings[0].compliance_id == "ccpa:do-not-sell-link"


def test_findings_from_soc2_emits_high_severity_for_trail_missing() -> None:
    report = Soc2CheckReport(
        trail_path="audit.log",
        entries_read=0,
        gates=(),
        issues=(
            Soc2Issue(
                category="trail-missing",
                description="trail not found.",
                compliance_id="soc2:trail-missing",
            ),
        ),
    )
    findings = findings_from_soc2(
        report,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_path="compliance/soc2_trail.json",
    )
    assert findings[0].severity == "high"
    assert findings[0].compliance_id == "soc2:trail-missing"


def test_findings_from_wcag22_emits_low_severity_for_redundant_entry() -> None:
    report = Wcag22CheckReport(
        signals_seen=True,
        issues=(
            Wcag22Issue(
                category="redundant-entry",
                success_criterion="3.3.7",
                route="/account",
                selector="#email-2",
                description="repeated email.",
                compliance_id="wcag-2.2:redundant-entry",
            ),
        ),
    )
    findings = findings_from_wcag22(
        report,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_path="compliance/wcag22.json",
    )
    assert findings[0].severity == "low"


def test_findings_from_reports_combines_every_check() -> None:
    g = GdprCheckReport(
        pages_checked=1,
        issues=(
            GdprIssue(
                category="asymmetric-consent",
                route="/",
                description="asym.",
                compliance_id="gdpr:EDPB-03/2022",
            ),
        ),
    )
    c = CcpaCheckReport(
        pages_checked=1,
        issues=(
            CcpaIssue(
                category="do-not-sell-link-missing",
                route="/",
                description="m.",
                compliance_id="ccpa:do-not-sell-link",
            ),
        ),
    )
    s = Soc2CheckReport(
        trail_path="audit.log",
        entries_read=1,
        gates=(),
        issues=(
            Soc2Issue(
                category="trail-non-monotonic",
                description="reorder.",
                compliance_id="soc2:trail-non-monotonic",
            ),
        ),
    )
    w = Wcag22CheckReport(
        signals_seen=True,
        issues=(
            Wcag22Issue(
                category="focus-obscured",
                success_criterion="2.4.11",
                description="overlap.",
                compliance_id="wcag-2.2:focus-not-obscured-min",
            ),
        ),
    )
    findings = findings_from_reports(
        gdpr=g,
        ccpa=c,
        soc2=s,
        wcag22=w,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_paths={
            "gdpr": "compliance/gdpr.json",
            "ccpa": "compliance/ccpa.json",
            "soc2": "compliance/soc2_trail.json",
            "wcag22": "compliance/wcag22.json",
        },
    )
    modules = {f.module for f in findings}
    assert modules == {"compliance"}
    categories = {f.category for f in findings}
    assert categories == {
        "compliance.gdpr.asymmetric-consent",
        "compliance.ccpa.do-not-sell-link-missing",
        "compliance.soc2.trail-non-monotonic",
        "compliance.wcag-2.2.focus-obscured",
    }


def test_findings_from_reports_handles_all_none_inputs() -> None:
    findings = findings_from_reports(
        gdpr=None,
        ccpa=None,
        soc2=None,
        wcag22=None,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_paths={},
    )
    assert findings == ()


def test_findings_from_reports_now_parameter_propagates() -> None:
    g = GdprCheckReport(
        pages_checked=1,
        issues=(
            GdprIssue(
                category="asymmetric-consent",
                route="/",
                description="asym.",
                compliance_id="gdpr:EDPB-03/2022",
            ),
        ),
    )
    pin = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    findings = findings_from_reports(
        gdpr=g,
        ccpa=None,
        soc2=None,
        wcag22=None,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://t.test",
        id_generator=_gen(),
        artifact_paths={"gdpr": "compliance/gdpr.json"},
        now=pin,
    )
    assert findings[0].created_at == pin
