"""Phase 34.04 — SOC 2 audit-trail gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from modules.compliance.soc2_trail import (
    Soc2TrailInputs,
    audit_soc2_trail,
    detect_secret_leaks,
)


def _write_trail(path: Path, entries: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")


def _clean_entries() -> list[dict[str, Any]]:
    """A fully-spec-compliant trail (all seven base gates pass)."""

    return [
        {"ts": "2026-05-31T00:00:01Z", "event": "policy_decision", "decision": "allow"},
        {
            "ts": "2026-05-31T00:00:02Z",
            "event": "module_start",
            "module": "accessibility",
        },
        {
            "ts": "2026-05-31T00:00:03Z",
            "event": "artifact_written",
            "artifact_path": "a11y/_.json",
        },
        {
            "ts": "2026-05-31T00:00:04Z",
            "event": "module_end",
            "module": "accessibility",
        },
    ]


def test_clean_trail_passes_every_base_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    _write_trail(trail, _clean_entries())
    report = audit_soc2_trail(trail)
    assert report.entries_read == 4
    assert report.all_gates_passed
    assert report.issues == ()


def test_missing_trail_fires_one_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    report = audit_soc2_trail(trail)
    assert not report.all_gates_passed
    categories = [issue.category for issue in report.issues]
    assert categories == ["trail-missing"]
    assert report.issues[0].compliance_id == "soc2:trail-missing"


def test_empty_trail_fires_trail_missing(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    trail.write_text("\n\n", encoding="utf-8")
    report = audit_soc2_trail(trail)
    assert [i.category for i in report.issues] == ["trail-missing"]


def test_non_jsonl_line_fires_not_jsonl_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    _write_trail(trail, entries)
    with trail.open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
    report = audit_soc2_trail(trail)
    categories = {issue.category for issue in report.issues}
    assert "trail-not-jsonl" in categories


def test_tampered_trail_fires_non_monotonic_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    # Insert an out-of-order timestamp into the middle of the log.
    entries.insert(
        2,
        {
            "ts": "2026-05-30T00:00:00Z",
            "event": "module_start",
            "module": "rogue",
        },
    )
    _write_trail(trail, entries)
    report = audit_soc2_trail(trail)
    categories = {issue.category for issue in report.issues}
    assert "trail-non-monotonic" in categories


def test_trail_missing_safety_decision_fires_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    # Strip the policy_decision entry.
    filtered = [e for e in entries if e.get("event") != "policy_decision"]
    _write_trail(trail, filtered)
    report = audit_soc2_trail(trail)
    categories = {issue.category for issue in report.issues}
    assert "trail-missing-safety-decision" in categories


def test_trail_missing_module_end_fires_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    filtered = [e for e in entries if e.get("event") != "module_end"]
    _write_trail(trail, filtered)
    report = audit_soc2_trail(
        trail,
        inputs=Soc2TrailInputs(expected_modules=("accessibility",)),
    )
    categories = {issue.category for issue in report.issues}
    assert "trail-missing-module-event" in categories


def test_trail_with_bearer_token_fires_secret_leak_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    entries.append(
        {
            "ts": "2026-05-31T00:00:05Z",
            "event": "request",
            "headers": "Authorization: Bearer abcdef1234567890qwertyuiop",
        }
    )
    _write_trail(trail, entries)
    report = audit_soc2_trail(trail)
    categories = {issue.category for issue in report.issues}
    assert "trail-secret-leak" in categories


def test_trail_with_redacted_bearer_passes_secret_leak_gate(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    entries.append(
        {
            "ts": "2026-05-31T00:00:05Z",
            "event": "request",
            "headers": "Authorization: [REDACTED:authorization_header]",
        }
    )
    _write_trail(trail, entries)
    report = audit_soc2_trail(trail)
    assert all(issue.category != "trail-secret-leak" for issue in report.issues)


def test_optional_llm_gate_only_runs_when_required(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    _write_trail(trail, _clean_entries())
    no_llm = audit_soc2_trail(trail, inputs=Soc2TrailInputs(require_llm_events=False))
    assert all(g.gate != "trail-llm-events" for g in no_llm.gates)
    with_llm = audit_soc2_trail(trail, inputs=Soc2TrailInputs(require_llm_events=True))
    assert any(g.gate == "trail-llm-events" for g in with_llm.gates)
    # And without an actual llm_call entry the optional gate fails.
    assert any(issue.category == "trail-missing-llm-event" for issue in with_llm.issues)


def test_optional_vault_gate_fires_when_required(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    _write_trail(trail, _clean_entries())
    report = audit_soc2_trail(
        trail,
        inputs=Soc2TrailInputs(require_vault_events=True),
    )
    categories = {issue.category for issue in report.issues}
    assert "trail-missing-vault-event" in categories


def test_optional_vault_gate_passes_when_entry_present(tmp_path: Path) -> None:
    trail = tmp_path / "audit.log"
    entries = _clean_entries()
    entries.append(
        {
            "ts": "2026-05-31T00:00:05Z",
            "event": "vault_access",
            "profile": "primary",
        }
    )
    _write_trail(trail, entries)
    report = audit_soc2_trail(
        trail,
        inputs=Soc2TrailInputs(require_vault_events=True),
    )
    categories = {issue.category for issue in report.issues}
    assert "trail-missing-vault-event" not in categories


def test_detect_secret_leaks_finds_jwt() -> None:
    lines = (
        '{"ts":"2026-05-31T00:00:00Z",'
        '"token":"eyJhbGciOiJIUzI1NiJ9.payloadpayload.sigsigsigsig"}',
    )
    hits = detect_secret_leaks(lines)
    assert len(hits) == 1


@pytest.mark.parametrize(
    "pattern",
    [
        "sk-abcdefghijklmnopqrstuv0123456789",
        "AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_detect_secret_leaks_finds_cloud_keys(pattern: str) -> None:
    assert detect_secret_leaks((pattern,))
