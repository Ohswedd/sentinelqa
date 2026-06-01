"""HTML + PR-comment LLM-audit section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.module_result import ModuleResult
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.reporter.html_writer import (
    HtmlReportInputs,
    build_template_context,
    render_html_report,
)
from engine.reporter.pr_comment import render_pr_comment


def _finding(rule_id: str, *, severity: str = "high") -> Finding:
    return Finding(
        id="FND-A1A2A3A4B5C6",
        run_id="RUN-AAAAAAAAAAAA",
        module="llm_audit",
        category=f"llm_audit_{rule_id.lower().replace('-', '_')}",
        severity=severity,  # type: ignore[arg-type]
        confidence=0.9,
        title=f"{rule_id} sample title",
        description="A sample LLM-audit finding for tests.",
        location=FindingLocation(route="http://localhost/dashboard"),
        evidence=(
            Evidence(
                id="EVD-A1A2A3A4B5C6",
                type="source_ref",
                path=Path("llm_audit/index.json"),
            ),
        ),
        affected_target="http://localhost/dashboard",
        created_at=datetime.now(UTC),
    )


def _run() -> TestRun:
    return TestRun(
        id="RUN-AAAAAAAAAAAA",
        target=Target(
            base_url="http://localhost:3000",  # type: ignore[arg-type]
            allowed_hosts=frozenset({"localhost"}),
            mode="safe",
        ),
        status="failed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )


def test_llm_audit_view_built_when_module_or_findings_present() -> None:
    findings = (_finding("DEAD-BTN"),)
    module_result = ModuleResult(
        id="MOD-A1A2A3A4B5C6",
        name="llm_audit",
        status="failed",
        findings=findings,
        metrics={},
        duration_ms=0,
        errors=(),
    )
    ctx = build_template_context(
        HtmlReportInputs(
            run=_run(),
            findings=findings,
            module_results=(module_result,),
        )
    )
    view = ctx["llm_audit"]
    assert view is not None
    assert view["total_findings"] == 1
    assert view["rules"][0]["category"].startswith("llm_audit_")


def test_llm_audit_view_none_when_no_module_no_findings() -> None:
    ctx = build_template_context(HtmlReportInputs(run=_run()))
    assert ctx["llm_audit"] is None


def test_html_renders_llm_audit_section() -> None:
    findings = (_finding("DEAD-BTN"),)
    module_result = ModuleResult(
        id="MOD-A1A2A3A4B5C6",
        name="llm_audit",
        status="failed",
        findings=findings,
        metrics={},
        duration_ms=0,
        errors=(),
    )
    html = render_html_report(
        HtmlReportInputs(
            run=_run(),
            findings=findings,
            module_results=(module_result,),
        )
    )
    assert "LLM-Code Audit" in html
    assert "llm_audit_dead_btn" in html


def test_html_omits_section_when_clean() -> None:
    html = render_html_report(HtmlReportInputs(run=_run()))
    assert "LLM-Code Audit" not in html


def test_pr_comment_renders_llm_audit_table_when_present() -> None:
    findings = [_finding("DEAD-BTN"), _finding("FAKE-ROUTE", severity="medium")]
    module_results = [
        ModuleResult(
            id="MOD-A1A2A3A4B5C6",
            name="llm_audit",
            status="failed",
            findings=tuple(findings),
            metrics={},
            duration_ms=0,
            errors=(),
        )
    ]
    body = render_pr_comment(
        _run(),
        findings,
        score=None,
        policy=None,
        module_results=module_results,
    )
    assert "LLM-Code Audit" in body
    assert "Category" in body


def test_pr_comment_skips_section_when_no_findings() -> None:
    body = render_pr_comment(
        _run(),
        [],
        score=None,
        policy=None,
        module_results=[],
    )
    assert "LLM-Code Audit" not in body
