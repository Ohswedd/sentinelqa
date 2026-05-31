"""Listing path: sidecar-only, never decrypts the storage state."""

from __future__ import annotations

from pathlib import Path

from engine.auth import Vault

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


def test_list_is_empty_on_a_fresh_vault(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    assert vault.list() == []


def test_list_returns_metadata_for_every_entry(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="a.com", name="one"))
    vault.put(_make_entry(host="b.com", name="two"))
    listed = vault.list()
    # Sorted by host, then name.
    assert [(m.host, m.name) for m in listed] == [
        ("a.com", "one"),
        ("b.com", "two"),
    ]
    # No storage state on the metadata view.
    for item in listed:
        assert not hasattr(item, "storage_state_json")


def test_list_skips_corrupt_sidecars(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="a.com", name="one"))
    # Corrupt the sidecar.
    sidecar = tmp_path / "a.com" / "one.json.meta"
    sidecar.write_text("{not json", encoding="utf-8")
    assert vault.list() == []


def test_list_filters_by_host(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="a.com", name="one"))
    vault.put(_make_entry(host="b.com", name="two"))
    listed = vault.list()
    just_a = [m for m in listed if m.host == "a.com"]
    assert len(just_a) == 1
