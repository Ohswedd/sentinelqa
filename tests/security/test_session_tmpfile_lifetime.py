"""Phase 31 — the materialized storage_state file MUST NOT outlive the run."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

from engine.auth import (
    Vault,
    cleanup_storage_state,
    materialize_storage_state,
    session_scope,
)

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


def test_tmpfile_uses_0600_permissions(tmp_path: Path) -> None:
    if sys.platform.startswith("win"):
        return
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
    assert stat.S_IMODE(handle.path.stat().st_mode) == 0o600
    parent_mode = stat.S_IMODE(handle.path.parent.stat().st_mode)
    # Auth subdir is at most 0o700 — never world-readable.
    assert (parent_mode & 0o077) == 0


def test_session_scope_removes_file_after_use(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    captured: Path | None = None
    with session_scope(
        vault,
        host="example.com",
        name="myorg",
        run_dir=run_dir,
        allowed_hosts={"example.com"},
    ) as handle:
        captured = handle.path
        assert captured.exists()
    assert captured is not None
    assert not captured.exists()
    # The auth/ directory is gone too — report uploaders never see it.
    assert not (run_dir / "auth").exists()


def test_cleanup_idempotent(tmp_path: Path) -> None:
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
    # Second call MUST NOT raise.
    cleanup_storage_state(handle)
