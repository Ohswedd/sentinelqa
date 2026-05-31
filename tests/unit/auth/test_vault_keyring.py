"""OS-keyring + passphrase-fallback behavior for :class:`KeyringStore`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from engine.auth.crypto import KEY_BYTES
from engine.auth.keyring_store import (
    KEYRING_ACCOUNT,
    KEYRING_SERVICE,
    KeyringStore,
    KeyringUnavailableError,
)


class FakeKeyring:
    """In-memory stand-in for the :mod:`keyring` library."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


def test_load_or_create_mints_and_persists_key(tmp_path: Path) -> None:
    backend = FakeKeyring()
    store = KeyringStore(backend=backend, salt_path=tmp_path / ".salt")
    key1 = store.load_or_create()
    assert len(key1.view()) == KEY_BYTES
    raw = backend.store[(KEYRING_SERVICE, KEYRING_ACCOUNT)]
    assert len(bytes.fromhex(raw)) == KEY_BYTES
    # A second call returns the SAME bytes (key is stable across calls).
    key2 = store.load_or_create()
    assert key1.view() == key2.view()


def test_load_existing_raises_when_no_keyring_and_no_salt(tmp_path: Path) -> None:
    store = KeyringStore(backend=None, salt_path=tmp_path / ".salt")
    with pytest.raises(KeyringUnavailableError):
        store.load_existing()


def test_passphrase_fallback_derives_stable_key(tmp_path: Path, monkeypatch: Any) -> None:
    salt = tmp_path / ".salt"
    store = KeyringStore(
        backend=None,
        salt_path=salt,
        passphrase_provider=lambda: "correct horse battery staple",
    )
    k1 = store.load_or_create()
    k2 = store.load_or_create()
    assert k1.view() == k2.view()
    # The salt was created on first call.
    assert salt.exists()


def test_passphrase_fallback_refuses_without_passphrase(tmp_path: Path) -> None:
    store = KeyringStore(
        backend=None,
        salt_path=tmp_path / ".salt",
        passphrase_provider=lambda: "",
    )
    with pytest.raises(KeyringUnavailableError):
        store.load_or_create()


def test_keyring_unreachable_raises(tmp_path: Path) -> None:
    class BrokenKeyring:
        def get_password(self, *_args: Any, **_kwargs: Any) -> str | None:
            raise RuntimeError("keyring backend is locked")

        def set_password(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def delete_password(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    store = KeyringStore(backend=BrokenKeyring(), salt_path=tmp_path / ".salt")
    with pytest.raises(KeyringUnavailableError):
        store.load_or_create()


def test_reset_clears_keyring_and_salt(tmp_path: Path) -> None:
    backend = FakeKeyring()
    store = KeyringStore(backend=backend, salt_path=tmp_path / ".salt")
    store.load_or_create()
    # Touch the salt path so reset sees it.
    salt = tmp_path / ".salt"
    salt.write_bytes(b"some-salt")
    store.reset()
    assert (KEYRING_SERVICE, KEYRING_ACCOUNT) not in backend.store
    assert not salt.exists()


def test_pbkdf2_iterations_floor_enforced(monkeypatch: Any) -> None:
    monkeypatch.setenv("SENTINEL_VAULT_PBKDF2_ITERATIONS", "1000")
    with pytest.raises(ValueError):
        KeyringStore(backend=None)


def test_pbkdf2_iterations_non_int_rejected(monkeypatch: Any) -> None:
    monkeypatch.setenv("SENTINEL_VAULT_PBKDF2_ITERATIONS", "not-a-number")
    with pytest.raises(ValueError):
        KeyringStore(backend=None)


def test_load_existing_returns_existing_keyring_entry(tmp_path: Path) -> None:
    backend = FakeKeyring()
    store = KeyringStore(backend=backend, salt_path=tmp_path / ".salt")
    minted = store.load_or_create()
    loaded = store.load_existing()
    assert loaded.view() == minted.view()


def test_load_from_keyring_rejects_malformed_hex(tmp_path: Path) -> None:
    backend = FakeKeyring()
    backend.store[(KEYRING_SERVICE, KEYRING_ACCOUNT)] = "not-hex!"
    store = KeyringStore(backend=backend, salt_path=tmp_path / ".salt")
    with pytest.raises(KeyringUnavailableError):
        store.load_or_create()


def test_load_from_keyring_rejects_wrong_size_key(tmp_path: Path) -> None:
    backend = FakeKeyring()
    backend.store[(KEYRING_SERVICE, KEYRING_ACCOUNT)] = "00" * (KEY_BYTES - 1)
    store = KeyringStore(backend=backend, salt_path=tmp_path / ".salt")
    with pytest.raises(KeyringUnavailableError):
        store.load_or_create()


def test_reset_is_safe_when_keyring_has_nothing(tmp_path: Path) -> None:
    backend = FakeKeyring()
    store = KeyringStore(backend=backend, salt_path=tmp_path / ".salt")
    store.reset()  # No prior entry; must not raise.


def test_passphrase_fallback_refuse_create_raises_without_salt(tmp_path: Path) -> None:
    store = KeyringStore(
        backend=None,
        salt_path=tmp_path / ".salt",
        passphrase_provider=lambda: "x" * 20,
    )
    with pytest.raises(KeyringUnavailableError):
        store.load_existing()
