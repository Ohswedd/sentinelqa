"""Audit log redaction: cookie / local-storage values can NEVER appear."""

from __future__ import annotations

import json
from pathlib import Path

from engine.auth import Vault, materialize_storage_state
from engine.policy.audit_log import read_audit_log, write_audit_entry
from engine.policy.redaction import redact

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


def test_session_used_audit_log_carries_counts_only(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    audit = run_dir / "audit.log"
    materialize_storage_state(
        vault,
        host="example.com",
        name="myorg",
        run_dir=run_dir,
        allowed_hosts={"example.com"},
        audit_log_path=audit,
    )
    lines = read_audit_log(audit)
    text = json.dumps(lines)
    # The known cookie value from the stub storage state must not be
    # echoed back into the audit log under any field.
    assert "sIcaLly_LoNg_session_value_abc123" not in text


def test_redactor_strips_cookie_header_lines() -> None:
    payload = {"message": "Cookie: session=abc123def456ghi789jkl0_long_value"}
    redacted = redact(payload)
    assert "abc123def456ghi789jkl0_long_value" not in json.dumps(redacted)


def test_redactor_collapses_storage_state_payload() -> None:
    raw = {
        "cookies": [{"name": "session", "value": "secret-cookie-payload-12345"}],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [{"name": "tok", "value": "secret-storage-value"}],
            }
        ],
    }
    audit_record = {"event": "auth.dump", "storage_state": raw}
    redacted = redact(audit_record)
    text = json.dumps(redacted)
    assert "secret-cookie-payload-12345" not in text
    assert "secret-storage-value" not in text


def test_write_audit_entry_round_trip_redacts(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    write_audit_entry(
        path,
        {
            "event": "auth.example",
            "set_cookie": "session=very_long_real_cookie_value_abcdef",
        },
    )
    lines = read_audit_log(path)
    text = json.dumps(lines)
    assert "very_long_real_cookie_value_abcdef" not in text
