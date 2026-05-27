"""Tests for the safety audit log writer."""

from __future__ import annotations

import json
from pathlib import Path

from engine.policy.audit_log import read_audit_log, write_audit_entry


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "audit.log"
    write_audit_entry(nested, {"allowed": True, "host": "localhost"})
    assert nested.exists()
    entries = read_audit_log(nested)
    assert entries[0]["host"] == "localhost"


def test_entries_are_jsonl(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    write_audit_entry(log, {"step": 1})
    write_audit_entry(log, {"step": 2})
    raw = log.read_text().splitlines()
    assert len(raw) == 2
    for line in raw:
        json.loads(line)


def test_secrets_redacted(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    write_audit_entry(log, {"password": "hunter2", "host": "localhost"})
    entries = read_audit_log(log)
    assert entries[0]["password"] == "[REDACTED:password]"


def test_timestamp_added(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    write_audit_entry(log, {"host": "localhost"})
    entries = read_audit_log(log)
    assert "ts" in entries[0]
