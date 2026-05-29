"""PR comment generator goldens (Phase 15.02)."""

from __future__ import annotations

from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.pr_comment import (
    PR_COMMENT_ANCHOR,
    PR_COMMENT_MAX_CHARS,
    render_pr_comment,
)

from tests.conftest import assert_matches_golden


def test_pr_comment_golden_passing(
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    body = render_pr_comment(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
        module_results=fixture_module_results_passing,
        changed_flows=("functional/login", "functional/signup"),
        artifact_url="https://example.com/run-artifact",
    )
    assert_matches_golden(body, goldens_root / "pr_comment.passing.golden.md")


def test_pr_comment_golden_blocked(
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_critical: tuple[Finding, ...],
    fixture_module_results_passing: tuple[ModuleResult, ...],
    fixture_quality_score_blocked: QualityScore,
    fixture_policy_decision_blocked: PolicyDecision,
) -> None:
    body = render_pr_comment(
        fixture_test_run_passed,
        fixture_findings_critical,
        fixture_quality_score_blocked,
        fixture_policy_decision_blocked,
        module_results=fixture_module_results_passing,
    )
    assert_matches_golden(body, goldens_root / "pr_comment.blocked.golden.md")


def test_pr_comment_starts_with_anchor(
    fixture_test_run_passed: TestRun,
) -> None:
    body = render_pr_comment(fixture_test_run_passed, (), None, None)
    assert body.startswith(PR_COMMENT_ANCHOR)
    assert body.endswith("\n")


def test_pr_comment_truncates_when_above_limit(
    fixture_test_run_passed: TestRun,
) -> None:
    flows = tuple(f"flow-{i}" for i in range(10_000))
    body = render_pr_comment(
        fixture_test_run_passed,
        (),
        None,
        None,
        changed_flows=flows,
    )
    assert len(body) <= PR_COMMENT_MAX_CHARS
    assert "Report truncated" in body
