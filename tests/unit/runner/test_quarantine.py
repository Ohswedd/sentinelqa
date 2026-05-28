"""Strict-validation tests for the quarantine list (08.04)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from engine.runner.quarantine import (
    Quarantine,
    QuarantineEntry,
    QuarantineError,
    QuarantineExpiredError,
    quarantine_to_findings,
)


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".quarantine.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_missing_file_yields_empty_quarantine(tmp_path: Path) -> None:
    quarantine = Quarantine.load(tmp_path / "missing.yaml")
    assert quarantine.entries == ()
    assert quarantine.test_ids() == ()


def test_valid_entry_loads(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    body = """
- test_id: "auth/login.spec.ts > sign in"
  reason: "Investigating flakiness on Safari"
  expires_at: 2026-06-04
  issue_url: https://github.com/Ohswedd/sentinelqa/issues/42
"""
    path = _write(tmp_path, body)
    quarantine = Quarantine.load(path, today=today)
    assert len(quarantine.entries) == 1
    [entry] = quarantine.entries
    assert isinstance(entry, QuarantineEntry)
    assert entry.test_id == "auth/login.spec.ts > sign in"
    assert "Investigating" in entry.reason


def test_expired_entry_is_rejected(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    body = """
- test_id: "old/test.spec.ts > broken"
  reason: "Was supposed to fix this last sprint"
  expires_at: 2026-05-20
  issue_url: https://example.com/issue/1
"""
    path = _write(tmp_path, body)
    with pytest.raises(QuarantineExpiredError) as info:
        Quarantine.load(path, today=today)
    assert "old/test.spec.ts > broken" in str(info.value)
    assert info.value.expired == ("old/test.spec.ts > broken",)


def test_too_far_future_is_rejected(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    far_future = today + timedelta(days=60)
    body = f"""
- test_id: "wait/forever.spec.ts > slow"
  reason: "Not fixing this for a while"
  expires_at: {far_future.isoformat()}
  issue_url: https://example.com/issue/2
"""
    path = _write(tmp_path, body)
    with pytest.raises(QuarantineError):
        Quarantine.load(path, today=today, max_age_days=14)


def test_non_url_issue_link_rejected(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    body = """
- test_id: "x"
  reason: "see jira"
  expires_at: 2026-06-04
  issue_url: jira-ticket-42
"""
    path = _write(tmp_path, body)
    with pytest.raises(QuarantineError):
        Quarantine.load(path, today=today)


def test_unknown_fields_rejected(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    body = """
- test_id: "x"
  reason: "valid reason here"
  expires_at: 2026-06-04
  issue_url: https://example.com/issue/3
  owner: alice
"""
    path = _write(tmp_path, body)
    with pytest.raises(QuarantineError):
        Quarantine.load(path, today=today)


def test_non_list_top_level_rejected(tmp_path: Path) -> None:
    body = "test_id: hi\n"
    path = _write(tmp_path, body)
    with pytest.raises(QuarantineError):
        Quarantine.load(path)


def test_quarantine_to_findings_redacts_evidence(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    body = """
- test_id: "auth/login.spec.ts > sign in"
  reason: "Investigating flakiness on Safari"
  expires_at: 2026-06-04
  issue_url: https://github.com/Ohswedd/sentinelqa/issues/42
"""
    path = _write(tmp_path, body)
    quarantine = Quarantine.load(path, today=today)
    findings = quarantine_to_findings(quarantine, module="functional", run_id="RUN-XYZ")
    assert len(findings) == 1
    finding = findings[0]
    assert finding["severity"] == "info"
    assert finding["evidence"]["issue_url"].startswith("https://")


def test_invalid_yaml_rejected(tmp_path: Path) -> None:
    body = "- test_id: oops\n  reason: 'unterminated"
    path = _write(tmp_path, body)
    with pytest.raises(QuarantineError):
        Quarantine.load(path)


def test_lookup_returns_entry(tmp_path: Path) -> None:
    today = date(2026, 5, 28)
    body = """
- test_id: "auth/login.spec.ts > sign in"
  reason: "Investigating flakiness on Safari"
  expires_at: 2026-06-04
  issue_url: https://github.com/Ohswedd/sentinelqa/issues/42
"""
    path = _write(tmp_path, body)
    quarantine = Quarantine.load(path, today=today)
    entry = quarantine.lookup("auth/login.spec.ts > sign in")
    assert entry is not None
    assert entry.issue_url.startswith("https://")
    assert quarantine.lookup("unknown") is None
