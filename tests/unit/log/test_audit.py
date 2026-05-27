"""Tests for engine.log.audit."""

from __future__ import annotations

from pathlib import Path

from engine.log.audit import log_audit
from engine.policy.audit_log import read_audit_log


def test_log_audit_writes_redacted(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    log_audit(log, {"host": "localhost", "password": "hunter2"})
    entries = read_audit_log(log)
    assert entries[0]["password"] == "[REDACTED:password]"


def test_log_audit_without_path_does_not_crash() -> None:
    # When the run lifecycle hasn't established a path yet (CLI bootstrap),
    # log_audit must still emit on the audit logger without raising.
    log_audit(None, {"host": "localhost"})
