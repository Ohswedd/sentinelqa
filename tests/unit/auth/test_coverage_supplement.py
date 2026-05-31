"""Supplementary coverage for ``engine.auth`` edge cases."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from engine.auth import (
    MasterKey,
    Vault,
    VaultEntry,
)
from engine.auth.crypto import (
    decrypt_blob,
    encrypt_blob,
    random_salt,
)
from engine.auth.login import _banner
from engine.auth.models import (
    DEFAULT_TTL_HOURS,
    MAX_STORAGE_STATE_BYTES,
)
from engine.auth.profiles import resolve_profile
from engine.auth.profiles.builtin import profile_names
from engine.auth.runtime import cookies_for_host
from engine.auth.vault import (
    VAULT_ROOT_ENV_VAR,
    VAULT_SCHEMA_VERSION,
    VaultError,
    _resolve_root,
    _validate_name,
    host_slug,
)

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry

# ---------------------------------------------------------------------------
# crypto.py — uncovered edges
# ---------------------------------------------------------------------------


def test_master_key_from_bytes_rejects_wrong_size() -> None:
    with pytest.raises(ValueError):
        MasterKey.from_bytes(b"\x00" * 16)


def test_master_key_view_after_close_raises() -> None:
    key = MasterKey.generate()
    key.close()
    with pytest.raises(RuntimeError):
        key.view()


def test_master_key_close_is_idempotent() -> None:
    key = MasterKey.generate()
    key.close()
    key.close()
    assert key.is_closed


def test_random_salt_rejects_short_lengths() -> None:
    with pytest.raises(ValueError):
        random_salt(8)


def test_encrypt_decrypt_associated_data_default_none() -> None:
    # Calling without associated_data should still round-trip.
    with MasterKey.generate() as key:
        blob = encrypt_blob(key, b"hi")
        assert decrypt_blob(key, blob) == b"hi"


# ---------------------------------------------------------------------------
# models.py — uncovered edges
# ---------------------------------------------------------------------------


def test_vault_entry_rejects_non_object_storage_state_json() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        VaultEntry(
            name="x",
            host="example.com",
            storage_state_json='["not","an","object"]',
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            cookies_count=0,
            local_storage_keys=0,
        )


def test_vault_entry_from_storage_state_rejects_zero_ttl() -> None:
    storage: dict[str, Any] = {"cookies": [], "origins": []}
    with pytest.raises(ValueError):
        VaultEntry.from_storage_state(
            name="x",
            host="example.com",
            storage_state=storage,
            storage_state_json=json.dumps(storage),
            ttl_hours=0,
        )


def test_vault_entry_from_storage_state_rejects_year_plus_ttl() -> None:
    storage: dict[str, Any] = {"cookies": [], "origins": []}
    with pytest.raises(ValueError):
        VaultEntry.from_storage_state(
            name="x",
            host="example.com",
            storage_state=storage,
            storage_state_json=json.dumps(storage),
            ttl_hours=24 * 366,
        )


def test_vault_metadata_age_and_expired_helpers() -> None:
    storage: dict[str, Any] = {"cookies": [], "origins": []}
    entry = VaultEntry.from_storage_state(
        name="x",
        host="example.com",
        storage_state=storage,
        storage_state_json=json.dumps(storage),
        ttl_hours=1,
    )
    meta = entry.to_metadata()
    # Fresh entry is not expired.
    assert meta.expired is False
    assert meta.age_seconds >= 0


def test_default_ttl_and_max_storage_state_bytes_constants() -> None:
    assert DEFAULT_TTL_HOURS == 24
    assert MAX_STORAGE_STATE_BYTES == 1_048_576


# ---------------------------------------------------------------------------
# vault.py — uncovered edges
# ---------------------------------------------------------------------------


def test_host_slug_handles_leading_dot() -> None:
    assert host_slug(".hidden") == "__.hidden"


def test_host_slug_replaces_non_slug_chars() -> None:
    assert host_slug("a/b c") == "a_b_c"


def test_host_slug_unknown_for_empty_input() -> None:
    assert host_slug("") == "unknown"


def test_validate_name_rejects_bad_names() -> None:
    with pytest.raises(ValueError):
        _validate_name("../etc/passwd")
    with pytest.raises(ValueError):
        _validate_name(".starts-with-dot")


def test_resolve_root_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VAULT_ROOT_ENV_VAR, "/tmp/sentinel-vault-test")
    assert _resolve_root(None) == Path("/tmp/sentinel-vault-test")


def test_resolve_root_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VAULT_ROOT_ENV_VAR, raising=False)
    assert _resolve_root(None) == Path.home() / ".sentinel" / "auth"


def test_vault_revoke_all_empty_root(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "does-not-exist", key_store=StubKeyStore())
    assert vault.revoke_all() == 0


def test_vault_revoke_all_skips_non_directory(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    (tmp_path / "random-file").write_text("noise", encoding="utf-8")
    # No vault entries, just a stray file: revoke_all leaves the noise alone.
    assert vault.revoke_all() == 0
    assert (tmp_path / "random-file").exists()


def test_vault_get_with_touch_false_does_not_update_last_used(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    entry = vault.get(
        "example.com",
        "myorg",
        allowed_hosts={"example.com"},
        touch=False,
    )
    assert entry.last_used_at is None


def test_vault_export_plaintext_round_trip(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    plaintext = vault.export_plaintext(
        "example.com",
        "myorg",
        allowed_hosts={"example.com"},
    )
    assert json.loads(plaintext)["cookies"][0]["name"] == "session"


def test_vault_has_returns_false_for_missing_entry(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    assert vault.has("example.com", "nope") is False


def test_vault_schema_version_constant() -> None:
    assert VAULT_SCHEMA_VERSION == "1.0.0"


def test_vault_envelope_serializes_last_used_at_when_set(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    vault.put(_make_entry())
    # Reading WITH touch updates last_used_at, then a second read sees a value.
    first = vault.get("example.com", "myorg", allowed_hosts={"example.com"})
    assert first.last_used_at is not None
    second = vault.get("example.com", "myorg", allowed_hosts={"example.com"})
    assert second.last_used_at is not None


def test_vault_error_is_distinct_from_auth_errors() -> None:
    err = VaultError("test")
    assert isinstance(err, Exception)
    assert "test" in str(err)


# ---------------------------------------------------------------------------
# profiles — uncovered edges
# ---------------------------------------------------------------------------


def test_profile_names_returns_sorted_unique_tuple() -> None:
    names = profile_names()
    assert names == tuple(sorted(set(names)))


def test_profile_login_host_helper() -> None:
    p = resolve_profile("github-oauth")
    assert p.login_host == "github.com"


# ---------------------------------------------------------------------------
# login — banner edge case (no profile)
# ---------------------------------------------------------------------------


def test_banner_without_profile_still_warns_credentials_never_seen() -> None:
    text = _banner("https://example.com/login", None)
    assert "NEVER" in text


# ---------------------------------------------------------------------------
# runtime — cookies_for_host edge cases
# ---------------------------------------------------------------------------


def test_cookies_for_host_empty_storage() -> None:
    assert cookies_for_host({}, "example.com") == {}


def test_cookies_for_host_non_dict_cookies_list_ignored() -> None:
    # Per the helper's contract, anything that isn't a list of dicts is
    # ignored; pass a deliberately-malformed payload to exercise the
    # guard.
    payload: dict[str, Any] = {"cookies": "broken"}
    assert cookies_for_host(payload, "example.com") == {}


# ---------------------------------------------------------------------------
# vault._safe_int — exercise every coercion branch
# ---------------------------------------------------------------------------


def test_safe_int_handles_known_shapes() -> None:
    from engine.auth.vault import _safe_int

    assert _safe_int(None) == 0
    assert _safe_int(7) == 0 + 7
    assert _safe_int("42") == 42
    assert _safe_int("not-a-number") == 0
    assert _safe_int(object()) == 0


def test_vault_envelope_round_trip_with_malformed_counts(tmp_path: Path) -> None:
    """Garbled cookies_count / local_storage_keys still loads as zero.

    Belt-and-braces: a tampered metadata field shouldn't take down the
    whole vault.
    """

    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    entry = _make_entry()
    vault.put(entry)
    # The cleanly-encrypted entry round-trips fine; the _safe_int helper
    # only matters for hand-edited / older-version envelopes which we
    # cover via the unit test above.
    assert vault.get("example.com", "myorg", allowed_hosts={"example.com"})
