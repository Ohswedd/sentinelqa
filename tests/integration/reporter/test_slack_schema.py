"""Slack payload validates against the vendored Block Kit schema."""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
from engine.domain.finding import Finding
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.slack import (
    SLACK_PAYLOAD_SCHEMA_PATH,
    load_block_kit_schema,
    render_slack_payload,
    write_slack_payload,
)


@pytest.fixture
def schema() -> dict:
    return load_block_kit_schema()


def test_schema_file_exists() -> None:
    assert SLACK_PAYLOAD_SCHEMA_PATH.exists()


def test_slack_payload_validates_passing(
    schema: dict,
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
    jsonschema.validate(payload, schema)


def test_slack_payload_validates_blocked(
    schema: dict,
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
    jsonschema.validate(payload, schema)


def test_slack_payload_validates_unsafe(
    schema: dict,
    fixture_test_run_unsafe: TestRun,
) -> None:
    payload = render_slack_payload(fixture_test_run_unsafe, (), None, None)
    jsonschema.validate(payload, schema)


def test_write_slack_payload(
    tmp_path: Path,
    fixture_test_run_passed: TestRun,
) -> None:
    payload = render_slack_payload(fixture_test_run_passed, (), None, None)
    written = write_slack_payload(tmp_path, payload)
    assert written.exists()
    assert written.name == "slack-summary.json"
    assert written.read_text(encoding="utf-8").endswith("\n")


def test_slack_payload_has_no_secret_paths(
    fixture_test_run_passed: TestRun,
) -> None:
    payload = render_slack_payload(fixture_test_run_passed, (), None, None)
    blocks = payload["blocks"]
    assert isinstance(blocks, list) and len(blocks) >= 1
    # No actions block when no artifact url.
    assert all(b.get("type") != "actions" for b in blocks)


def test_slack_payload_includes_artifact_action(
    fixture_test_run_passed: TestRun,
) -> None:
    payload = render_slack_payload(
        fixture_test_run_passed, (), None, None, artifact_url="https://example.com/r"
    )
    blocks = payload["blocks"]
    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    assert actions[0]["elements"][0]["url"] == "https://example.com/r"
