"""Self-test: the HTML report passes our own structural a11y checks (15.07).

The accessibility module runs axe-core inside a browser, which
is too heavy for a unit test. This test takes the lighter-weight path:
it renders ``report.html`` and verifies the structural-a11y rules we
encode in :mod:`modules.accessibility.checks.landmarks` and
:mod:`modules.accessibility.checks.sr_names` (no browser required):

- A ``<main>`` landmark is present.
- A skip-link points to the main landmark.
- Every ``<img>`` has a non-empty ``alt`` attribute.
- Every form control (``<select>`` / ``<input>``) has either a wrapping
 ``<label>`` or an ``aria-label`` / ``aria-labelledby`` reference.
- Headings hierarchy does not skip more than one level at a time.

The intent is the same as the spec gate: "our own report passes our own
accessibility checks." Axe-core in CI runs (a11y module) is
still the comprehensive guard.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.html_writer import HtmlReportInputs, render_html_report


def _render(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> BeautifulSoup:
    body = render_html_report(
        HtmlReportInputs(
            run=fixture_test_run_passed,
            findings=fixture_findings_mixed,
            module_results=fixture_module_results_passing,
            score=fixture_quality_score_passing,
            policy=fixture_policy_decision_pass,
        )
    )
    return BeautifulSoup(body, "html.parser")


def test_html_has_lang_attribute(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    html_tag = soup.find("html")
    assert isinstance(html_tag, Tag)
    assert html_tag.get("lang") == "en"


def test_html_has_main_landmark(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    main = soup.find("main")
    assert isinstance(main, Tag)
    assert main.get("id") == "main-content"


def test_html_has_working_skip_link(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    skip = soup.find("a", class_="skip-link")
    assert isinstance(skip, Tag)
    href = skip.get("href")
    assert href == "#main-content"


def test_html_images_have_alt_text(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    for img in soup.find_all("img"):
        assert isinstance(img, Tag)
        alt = img.get("alt")
        assert isinstance(alt, str)
        assert alt.strip(), f"<img> missing alt text: {img}"


def test_html_form_controls_have_accessible_names(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    for control in soup.find_all(["select", "input"]):
        assert isinstance(control, Tag)
        if control.get("type") in {"hidden"}:
            continue
        has_label = control.find_parent("label") is not None
        aria_label = control.get("aria-label")
        aria_labelledby = control.get("aria-labelledby")
        assert (
            has_label or aria_label or aria_labelledby
        ), f"form control without accessible name: {control}"


def test_html_headings_are_hierarchical(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    headings: list[int] = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if isinstance(tag, Tag):
            headings.append(int(tag.name[1]))
    assert headings, "no headings rendered"
    assert headings[0] == 1
    seen_max = headings[0]
    for level in headings[1:]:
        assert level <= seen_max + 1, f"heading jumps from {seen_max} to {level}"
        seen_max = max(seen_max, level)


def test_html_aria_labelledby_targets_exist(
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    soup = _render(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_module_results_passing,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
    )
    ids = {tag.get("id") for tag in soup.find_all(attrs={"id": True}) if isinstance(tag, Tag)}
    for tag in soup.find_all(attrs={"aria-labelledby": True}):
        if not isinstance(tag, Tag):
            continue
        ref = tag.get("aria-labelledby")
        assert isinstance(ref, str)
        assert ref in ids, f"aria-labelledby references missing id {ref!r}"
