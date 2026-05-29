"""``sentinelqa.agent.format`` and the per-entity message builders."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.repair_suggestion import RepairSuggestion

from sentinelqa.agent import (
    AGENT_MESSAGE_SCHEMA_VERSION,
    finding_to_agent_message,
    format,
    repair_suggestion_to_agent_message,
)


@pytest.fixture
def finding() -> Finding:
    return Finding(
        id="FND-AAAAAAAAAAAA",
        run_id="RUN-AAAAAAAAAAAA",
        module="security",
        category="security/headers",
        severity="high",
        confidence=0.9,
        title="Cookie missing HttpOnly",
        description="Session cookie does not set HttpOnly.",
        location=FindingLocation(route="/login"),
        evidence=(
            Evidence(
                id="EVD-AAAAAAAAAAAA",
                type="network_log",
                path=Path("traces/login.har"),
                redacted=True,
            ),
        ),
        recommendation="Set HttpOnly on the session cookie.",
        created_at=datetime(2026, 5, 29, 12, 0, tzinfo=UTC),
    )


def test_finding_agent_message_shape(finding: Finding) -> None:
    msg = finding_to_agent_message(finding)
    assert msg["type"] == "finding"
    assert msg["agent_message_schema_version"] == AGENT_MESSAGE_SCHEMA_VERSION
    assert msg["id"] == "FND-AAAAAAAAAAAA"
    assert msg["module"] == "security"
    assert msg["severity"] == "high"
    assert msg["confidence"] == 0.9
    assert msg["title"] == "Cookie missing HttpOnly"
    assert msg["location"] == {
        "route": "/login",
        "selector": None,
        "file": None,
        "line": None,
    }
    assert msg["evidence_paths"] == ["traces/login.har"]


def test_finding_to_agent_message_method_matches_helper(finding: Finding) -> None:
    assert finding.to_agent_message() == finding_to_agent_message(finding)


def test_repair_suggestion_message_shape() -> None:
    suggestion = RepairSuggestion(
        id="RPR-AAAAAAAAAAAA",
        target_test="tests/sentinel/login.spec.ts",
        original="page.locator('button.signin')",
        proposed="page.getByRole('button', { name: /sign in/i })",
        confidence=0.85,
        reason="Class-based selector is brittle; semantic role + name is stable.",
        evidence=(
            Evidence(
                id="EVD-AAAAAAAAAAAA",
                type="screenshot",
                path=Path("screenshots/login.png"),
                redacted=True,
            ),
        ),
        requires_human_review=True,
    )
    msg = repair_suggestion_to_agent_message(suggestion)
    assert msg["type"] == "repair_suggestion"
    assert msg["agent_message_schema_version"] == AGENT_MESSAGE_SCHEMA_VERSION
    assert msg["original"] == "page.locator('button.signin')"
    assert msg["proposed"] == "page.getByRole('button', { name: /sign in/i })"
    assert msg["confidence"] == 0.85
    assert msg["requires_human_review"] is True
    assert msg["evidence_paths"] == ["screenshots/login.png"]
    # Suggestion's own method must match the helper.
    assert suggestion.to_agent_message() == msg


def test_format_ndjson_is_newline_delimited(finding: Finding) -> None:
    out = format([finding_to_agent_message(finding)], format="ndjson")
    assert "\n" not in out  # single message -> no newline
    # Round-trips through JSON.
    parsed = json.loads(out)
    assert parsed["id"] == finding.id


def test_format_ndjson_multiple_messages(finding: Finding) -> None:
    msgs = [finding_to_agent_message(finding), finding_to_agent_message(finding)]
    out = format(msgs, format="ndjson")
    lines = out.split("\n")
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line is valid JSON


def test_format_jsonl_alias_matches_ndjson(finding: Finding) -> None:
    msgs = [finding_to_agent_message(finding)]
    assert format(msgs, format="jsonl") == format(msgs, format="ndjson")


def test_format_list_returns_json_array(finding: Finding) -> None:
    msgs = [finding_to_agent_message(finding)]
    out = format(msgs, format="list")
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert parsed[0]["id"] == finding.id


def test_format_rejects_unknown_format(finding: Finding) -> None:
    with pytest.raises(ValueError, match="unknown format"):
        format([finding_to_agent_message(finding)], format="yaml")  # type: ignore[arg-type]


def test_format_is_deterministic(finding: Finding) -> None:
    msgs = [finding_to_agent_message(finding)]
    a = format(msgs, format="ndjson")
    b = format(msgs, format="ndjson")
    assert a == b
