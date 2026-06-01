"""HTML report self-contained guarantee (Phase 15.01).

The report MUST work offline: no external URLs, no CDN references, no
`http(s)://` references in `<link>` / `<script>` / `<img>` / `<iframe>`
tags. The only network references allowed are within finding evidence
that the report explicitly redacts or shows as text.

The test scans the rendered HTML body for any embedded resource URL and
fails the build if it sees one. This is the offline guarantee from
our engineering rules + our product spec7.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.html_writer import (
    HTML_REPORT_SCHEMA_VERSION,
    HtmlReportInputs,
    render_html_report,
    write_html,
)

_EXTERNAL_RESOURCE_PATTERNS = (
    re.compile(r"<link[^>]+href=[\"']([^\"']+)[\"']", re.IGNORECASE),
    re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE),
    re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE),
    re.compile(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE),
    re.compile(r"url\(\s*[\"']?(http[^)\"']+)[\"']?\s*\)", re.IGNORECASE),
)


def _is_external(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme:
        return False
    if parsed.scheme in {"data", "file"}:
        return False
    return parsed.scheme in {"http", "https", "ws", "wss"}


def test_html_template_has_no_external_resource_urls(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    body = render_html_report(
        HtmlReportInputs(
            run=fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
            config_digest="sha256:test",
        )
    )
    for pattern in _EXTERNAL_RESOURCE_PATTERNS:
        for match in pattern.finditer(body):
            url = match.group(1).strip()
            assert not _is_external(url), (
                f"HTML report references external URL {url!r}; "
                "report must be offline-capable (CLAUDE §41)."
            )


def test_html_writer_emits_one_file(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    inputs = HtmlReportInputs(run=fixture_test_run_passed)
    path = write_html(artifacts, inputs)
    assert path.name == "report.html"
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    # CSS + JS inlined
    assert "<style>" in body
    assert "<script>" in body
    assert "color-scheme: light dark" in body
    assert "wireFindings" in body


def test_html_schema_version_in_footer(
    fixture_test_run_passed: TestRun,
) -> None:
    body = render_html_report(HtmlReportInputs(run=fixture_test_run_passed))
    assert HTML_REPORT_SCHEMA_VERSION in body


def test_html_includes_target_safety_note(
    fixture_test_run_passed: TestRun,
) -> None:
    body = render_html_report(HtmlReportInputs(run=fixture_test_run_passed))
    assert "authorized testing" in body


def test_html_renders_for_unsafe_run(
    fixture_test_run_unsafe: TestRun,
) -> None:
    body = render_html_report(HtmlReportInputs(run=fixture_test_run_unsafe))
    assert "UNSAFE TARGET" in body or "unsafe_target_rejected" in body
    assert "n/a" in body  # score hidden


@pytest.mark.parametrize(
    "fixture_name",
    ["fixture_test_run_passed", "fixture_test_run_unsafe", "fixture_test_run_dry"],
)
def test_html_render_is_deterministic(
    request: pytest.FixtureRequest,
    fixture_name: str,
) -> None:
    run: TestRun = request.getfixturevalue(fixture_name)
    inputs = HtmlReportInputs(run=run, config_digest="sha256:abc")
    first = render_html_report(inputs)
    second = render_html_report(inputs)
    assert first == second
