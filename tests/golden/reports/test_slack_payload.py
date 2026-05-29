"""Slack summary payload goldens (Phase 15.06)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.domain.finding import Finding
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.slack import render_slack_payload

from tests.conftest import assert_matches_golden


def _to_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def test_slack_payload_golden_passing(
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_mixed: tuple[Finding, ...],
    fixture_quality_score_passing: QualityScore,
    fixture_policy_decision_pass: PolicyDecision,
) -> None:
    payload = render_slack_payload(
        fixture_test_run_passed,
        fixture_findings_mixed,
        fixture_quality_score_passing,
        fixture_policy_decision_pass,
        artifact_url="https://example.com/report",
    )
    assert_matches_golden(_to_text(payload), goldens_root / "slack.passing.golden.json")


def test_slack_payload_golden_blocked(
    goldens_root: Path,
    fixture_test_run_passed: TestRun,
    fixture_findings_critical: tuple[Finding, ...],
    fixture_quality_score_blocked: QualityScore,
    fixture_policy_decision_blocked: PolicyDecision,
) -> None:
    payload = render_slack_payload(
        fixture_test_run_passed,
        fixture_findings_critical,
        fixture_quality_score_blocked,
        fixture_policy_decision_blocked,
    )
    assert_matches_golden(_to_text(payload), goldens_root / "slack.blocked.golden.json")


def test_slack_payload_golden_unsafe(
    goldens_root: Path,
    fixture_test_run_unsafe: TestRun,
) -> None:
    payload = render_slack_payload(
        fixture_test_run_unsafe,
        (),
        None,
        None,
    )
    assert_matches_golden(_to_text(payload), goldens_root / "slack.unsafe.golden.json")
