"""AEAD round-trip, tamper detection, expiry, file permissions."""

from __future__ import annotations

import json
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from engine.auth import MasterKey, Vault, VaultEntry
from engine.auth.crypto import CryptoError, decrypt_blob, encrypt_blob
from engine.errors.base import (
    VaultEntryExpiredError,
    VaultEntryNotFoundError,
    VaultHostMismatchError,
    VaultIntegrityError,
)


class StubKeyStore:
    """In-memory master-key holder used by the unit tests."""

    def __init__(self, key: MasterKey | None = None) -> None:
        self.key = key or MasterKey.generate()
        # Snapshot the bytes once so we can hand out fresh MasterKey
        # instances on every load (the Vault closes the key after each
        # call as a defense-in-depth measure).
        self._material = self.key.view()

    def load_or_create(self) -> MasterKey:
        return MasterKey.from_bytes(self._material)

    def load_existing(self) -> MasterKey:
        return MasterKey.from_bytes(self._material)

    def reset(self) -> None:
        self._material = b"\x00" * 32


def _storage_state() -> dict[str, object]:
    return {
        "cookies": [
            {
                "name": "session",
                "value": "sIcaLly_LoNg_session_value_abc123",
                "domain": "example.com",
                "path": "/",
            }
        ],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [{"name": "k", "value": "v"}],
            }
        ],
    }


def _make_entry(host: str = "example.com", name: str = "myorg") -> VaultEntry:
    storage = _storage_state()
    return VaultEntry.from_storage_state(
        name=name,
        host=host,
        storage_state=storage,
        storage_state_json=json.dumps(storage, sort_keys=True),
        ttl_hours=24,
    )


def test_encrypt_decrypt_round_trip() -> None:
    with MasterKey.generate() as key:
        blob = encrypt_blob(key, b"hello", associated_data=b"ctx")
        assert decrypt_blob(key, blob, associated_data=b"ctx") == b"hello"


def test_decrypt_wrong_aad_fails() -> None:
    with MasterKey.generate() as key:
        blob = encrypt_blob(key, b"hello", associated_data=b"ctx")
        with pytest.raises(CryptoError):
            decrypt_blob(key, blob, associated_data=b"other-ctx")


def test_decrypt_wrong_key_fails() -> None:
    with MasterKey.generate() as k1, MasterKey.generate() as k2:
        blob = encrypt_blob(k1, b"hello")
        with pytest.raises(CryptoError):
            decrypt_blob(k2, blob)


def test_decrypt_short_blob_rejected() -> None:
    with MasterKey.generate() as key, pytest.raises(CryptoError):
        decrypt_blob(key, b"too-short")


def test_vault_put_and_get_round_trip(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    entry = _make_entry()
    vault.put(entry)
    got = vault.get("example.com", "myorg", allowed_hosts={"example.com"})
    assert got.host == "example.com"
    assert got.cookies_count == 1
    assert got.local_storage_keys == 1
    assert got.last_used_at is not None


def test_vault_file_has_0600_permissions(tmp_path: Path) -> None:
    if sys.platform.startswith("win"):
        pytest.skip("POSIX file modes are no-ops on Windows")
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    path = vault.put(_make_entry())
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_vault_get_refuses_unknown_entry(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    with pytest.raises(VaultEntryNotFoundError):
        vault.get("example.com", "nope", allowed_hosts={"example.com"})


def test_vault_get_refuses_non_allowlisted_host(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    with pytest.raises(VaultHostMismatchError) as info:
        vault.get("example.com", "myorg", allowed_hosts={"other.com"})
    assert info.value.code == "E-AUTH-003"


def test_vault_get_refuses_expired_entry(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    far_future = datetime.now(UTC) + timedelta(days=400)
    with pytest.raises(VaultEntryExpiredError) as info:
        vault.get(
            "example.com",
            "myorg",
            allowed_hosts={"example.com"},
            now=far_future,
        )
    assert info.value.code == "E-AUTH-002"


def test_vault_get_detects_tamper(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    target = vault.put(_make_entry())
    data = bytearray(target.read_bytes())
    data[-1] ^= 0x01  # flip a tag byte
    target.write_bytes(data)
    with pytest.raises(VaultIntegrityError) as info:
        vault.get("example.com", "myorg", allowed_hosts={"example.com"})
    assert info.value.code == "E-AUTH-004"


def test_vault_revoke_removes_entry_and_sidecar(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    assert vault.has("example.com", "myorg") is True
    removed = vault.revoke("example.com", "myorg")
    assert removed is True
    assert vault.has("example.com", "myorg") is False
    # Sidecar gone, host dir pruned.
    assert list(tmp_path.glob("**/myorg.json.meta")) == []
    assert list(tmp_path.glob("example.com")) == []


def test_vault_revoke_missing_entry_is_idempotent(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    assert vault.revoke("example.com", "nope") is False


def test_vault_revoke_all_removes_every_entry(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry(host="a.com", name="one"))
    vault.put(_make_entry(host="b.com", name="two"))
    assert vault.revoke_all() == 2
    assert vault.list() == []


def test_vault_put_refuses_duplicate_without_force(tmp_path: Path) -> None:
    from engine.auth.vault import VaultError

    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    with pytest.raises(VaultError):
        vault.put(_make_entry())


def test_vault_put_overwrites_with_force(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    vault.put(_make_entry(), force=True)


def test_vault_list_redacts_payload(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    metadata = vault.list()
    assert len(metadata) == 1
    item = metadata[0]
    assert item.host == "example.com"
    assert item.cookies_count == 1
    assert not hasattr(item, "storage_state_json")
