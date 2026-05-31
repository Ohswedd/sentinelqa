"""Vault refuses to surface a session for a non-allowlisted host."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.auth import Vault
from engine.errors.base import VaultHostMismatchError

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


def test_vault_refuses_when_host_not_in_allowlist(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="trusted.example", name="ok"))
    # Operator runs a scan against a different target whose allowlist
    # does NOT include `trusted.example` — the vault must refuse.
    with pytest.raises(VaultHostMismatchError) as info:
        vault.get(
            "trusted.example",
            "ok",
            allowed_hosts={"other.example"},
        )
    assert info.value.code == "E-AUTH-003"


def test_vault_refuses_when_allowlist_is_empty(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="trusted.example", name="ok"))
    with pytest.raises(VaultHostMismatchError):
        vault.get("trusted.example", "ok", allowed_hosts=set())


def test_vault_uses_case_insensitive_host_compare(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="trusted.example", name="ok"))
    got = vault.get("trusted.example", "ok", allowed_hosts={"Trusted.Example"})
    assert got.host == "trusted.example"
