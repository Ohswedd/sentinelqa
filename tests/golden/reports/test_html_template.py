"""Golden test for the HTML report (Phase 15.01).

The HTML body is byte-locked against `report.passing.golden.html` so
template drift is impossible without an explicit golden update. Use
`make update-goldens` (or `SENTINELQA_UPDATE_GOLDENS=1 pytest ...`) to
regenerate the golden when an intentional change lands.

To keep the golden small + reviewable we strip the inline CSS + JS
(which would otherwise dominate the diff) by replacing the contents of
the `<style>` and `<script>` tags with stable placeholders. That lets
the golden focus on the template structure + content while still
proving determinism — the raw assets get their own targeted assertions
in :mod:`tests.integration.reporter.test_html_self_contained`.
"""

from __future__ import annotations

import re
from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.html_writer import HtmlReportInputs, render_html_report

from tests.conftest import assert_matches_golden

_STYLE_BLOCK = re.compile(r"(<style>)([\s\S]*?)(</style>)", re.IGNORECASE)
_SCRIPT_BLOCK = re.compile(r"(<script>)([\s\S]*?)(</script>)", re.IGNORECASE)


def _scrub(body: str) -> str:
    scrubbed = _STYLE_BLOCK.sub(r"\1<inline_css>\3", body)
    return _SCRIPT_BLOCK.sub(r"\1<inline_js>\3", scrubbed)


def test_html_report_golden_passing(
    goldens_root: Path,
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
            config_digest="sha256:goldena1b2c3",
        )
    )
    assert_matches_golden(_scrub(body), goldens_root / "html" / "report.passing.golden.html")


def test_html_report_golden_unsafe(
    goldens_root: Path,
    fixture_test_run_unsafe: TestRun,
) -> None:
    body = render_html_report(
        HtmlReportInputs(
            run=fixture_test_run_unsafe,
            config_digest="sha256:goldenunsafe",
        )
    )
    assert_matches_golden(_scrub(body), goldens_root / "html" / "report.unsafe.golden.html")


def test_html_report_golden_dry_run(
    goldens_root: Path,
    fixture_test_run_dry: TestRun,
) -> None:
    body = render_html_report(
        HtmlReportInputs(
            run=fixture_test_run_dry,
            config_digest="sha256:goldendryrun",
        )
    )
    assert_matches_golden(_scrub(body), goldens_root / "html" / "report.dry_run.golden.html")
