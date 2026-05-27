"""Golden tests for the Markdown report (task 03.06)."""

from __future__ import annotations

from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.markdown_writer import md_escape, render_markdown, write_markdown

from tests.conftest import assert_matches_golden


def test_markdown_golden_passing(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_markdown(
        artifacts,
        fixture_test_run_passed,
        findings=fixture_findings_mixed,
        module_results=fixture_module_results_passing,
        score=fixture_quality_score_passing,
        policy=fixture_policy_decision_pass,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "markdown.passing.golden.md")


def test_markdown_golden_blocked(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_critical: tuple[Finding, ...],
    fixture_module_results_blocked: tuple[ModuleResult, ...],
    fixture_quality_score_blocked: QualityScore,
    fixture_policy_decision_blocked: PolicyDecision,
) -> None:
    # Reuse fixture_test_run_passed (status="passed") but pair with blocked
    # policy + score; the markdown writer trusts PolicyDecision authoritatively.
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_passed.id)
    written = write_markdown(
        artifacts,
        fixture_test_run_passed,
        findings=fixture_findings_critical,
        module_results=fixture_module_results_blocked,
        score=fixture_quality_score_blocked,
        policy=fixture_policy_decision_blocked,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "markdown.blocked.golden.md")


def test_markdown_golden_unsafe(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_unsafe: TestRun,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_unsafe.id)
    written = write_markdown(
        artifacts,
        fixture_test_run_unsafe,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "markdown.unsafe.golden.md")


def test_markdown_golden_dry_run(
    tmp_path: Path,
    goldens_root: Path,
    fixture_test_run_dry: TestRun,
) -> None:
    artifacts = ArtifactDirectory.create(tmp_path, fixture_test_run_dry.id)
    written = write_markdown(
        artifacts,
        fixture_test_run_dry,
    )
    actual = written.read_text(encoding="utf-8")
    assert_matches_golden(actual, goldens_root / "markdown.dry_run.golden.md")


def test_md_escape_neutralizes_markdown_injection() -> None:
    raw = (
        "Title with [link](http://evil.example.com) and _italic_ and `code`"
        "and *bold* and ![img](x) and | pipe"
    )
    escaped = md_escape(raw)
    # All Markdown control chars are backslash-prefixed.
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "\\(" in escaped
    assert "\\)" in escaped
    assert "\\_" in escaped
    assert "\\`" in escaped
    assert "\\*" in escaped
    assert "\\!" in escaped
    assert "\\|" in escaped


def test_render_markdown_injects_escaped_titles(
    fixture_test_run_passed: TestRun,
    fixture_finished_at: object,
) -> None:
    from datetime import datetime

    from engine.domain.finding import FindingLocation

    assert isinstance(fixture_finished_at, datetime)

    finding = Finding(
        id="FND-INJECTAAAAAA",
        run_id=fixture_test_run_passed.id,
        module="security",
        category="security/headers",
        severity="critical",
        confidence=0.95,
        title="Naughty [click here](http://evil.example.com) title",
        description="Some description with [hostile](http://evil.example.com) markup.",
        location=FindingLocation(),
        evidence=(),
        recommendation="Patch.",
        affected_target="https://localhost:8080",
        created_at=fixture_finished_at,
    )
    out = render_markdown(fixture_test_run_passed, findings=(finding,))
    # Bracket/parenthesis chars from the malicious title appear backslash-escaped.
    assert "\\[click here\\]" in out
    assert "http://evil.example.com" not in out or "\\(http" in out
