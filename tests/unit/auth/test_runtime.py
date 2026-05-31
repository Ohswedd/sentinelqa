"""Runtime helpers: materialize → cleanup, in-memory load, cookie filter."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from engine.auth import (
    Vault,
    cleanup_storage_state,
    cookies_for_host,
    load_storage_state_dict,
    materialize_storage_state,
    session_scope,
)
from engine.policy.audit_log import read_audit_log

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


def test_materialize_writes_0600_file_and_audit_log(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    audit = run_dir / "audit.log"
    handle = materialize_storage_state(
        vault,
        host="example.com",
        name="myorg",
        run_dir=run_dir,
        allowed_hosts={"example.com"},
        audit_log_path=audit,
    )
    assert handle.path.exists()
    if not sys.platform.startswith("win"):
        assert stat.S_IMODE(handle.path.stat().st_mode) == 0o600
    audit_lines = read_audit_log(audit)
    assert any(e.get("event") == "auth.session_used" for e in audit_lines)


def test_cleanup_removes_file_and_directory(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    handle = materialize_storage_state(
        vault,
        host="example.com",
        name="myorg",
        run_dir=run_dir,
        allowed_hosts={"example.com"},
    )
    cleanup_storage_state(handle)
    assert not handle.path.exists()
    assert not (run_dir / "auth").exists()


def test_session_scope_cleans_up_on_exception(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with (
        pytest.raises(RuntimeError),
        session_scope(
            vault,
            host="example.com",
            name="myorg",
            run_dir=run_dir,
            allowed_hosts={"example.com"},
        ) as handle,
    ):
        assert handle.path.exists()
        raise RuntimeError("boom")
    assert not handle.path.exists()


def test_load_storage_state_dict_audits_use(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry())
    audit = tmp_path / "audit.log"
    payload = load_storage_state_dict(
        vault,
        host="example.com",
        name="myorg",
        allowed_hosts={"example.com"},
        audit_log_path=audit,
    )
    assert isinstance(payload, dict)
    audit_lines = read_audit_log(audit)
    assert any(e.get("event") == "auth.session_used" for e in audit_lines)


def test_cookies_for_host_matches_domain_exactly() -> None:
    storage = {
        "cookies": [
            {"name": "a", "value": "1", "domain": "example.com"},
            {"name": "b", "value": "2", "domain": ".sub.example.com"},
            {"name": "c", "value": "3", "domain": "other.com"},
        ]
    }
    assert cookies_for_host(storage, "example.com") == {"a": "1"}
    assert cookies_for_host(storage, "sub.example.com") == {"a": "1", "b": "2"}
    assert cookies_for_host(storage, "other.com") == {"c": "3"}
    assert cookies_for_host(storage, "unrelated.com") == {}


def test_cookies_for_host_ignores_malformed_entries() -> None:
    storage = {
        "cookies": [
            "not-a-dict",
            {"name": "a"},  # missing value
            {"value": "v"},  # missing name
            {"name": "x", "value": "y", "domain": ""},  # empty domain
            {"name": "ok", "value": "v", "domain": "example.com"},
        ]
    }
    assert cookies_for_host(storage, "example.com") == {"ok": "v"}
