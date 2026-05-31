"""Unit-level coverage for :func:`engine.auth.login.capture_session`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from engine.auth import (
    LoginRequest,
    Vault,
    capture_session,
    resolve_profile,
)
from engine.auth.login import _banner, host_pair_from_login_url, hosts_iterable
from engine.errors.base import (
    AuthCommandForbiddenInCiError,
    LoginOriginChangedError,
)
from engine.policy.audit_log import read_audit_log

from tests.unit.auth.test_vault_crypto import StubKeyStore


class StubLauncher:
    """Returns a fixed (storage_state, landed_url) pair."""

    def __init__(self, storage_state: dict[str, Any], landed_url: str) -> None:
        self._storage_state = storage_state
        self._landed_url = landed_url

    def capture(
        self,
        *,
        login_url: str,
        browser: str,
        confirm: Callable[[str], str],
    ) -> tuple[dict[str, Any], str]:
        # Drive the confirm callback so we exercise that path.
        confirm("press enter > ")
        return self._storage_state, self._landed_url


def _request(
    *,
    name: str = "github-myorg",
    login_url: str = "https://github.com/login",
    target_host: str = "github.com",
    allowed: tuple[str, ...] = ("github.com",),
    ci: bool = False,
    audit: Path | None = None,
) -> LoginRequest:
    return LoginRequest(
        name=name,
        login_url=login_url,
        target_host=target_host,
        allowed_hosts=allowed,
        profile=None,
        browser="chromium",
        ttl_hours=24,
        force=False,
        ci=ci,
        audit_log_path=audit,
    )


def test_capture_session_writes_entry_and_audit_log(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    storage = {
        "cookies": [
            {
                "name": "user_session",
                "value": "long-session-value-abc123",
                "domain": "github.com",
            }
        ],
        "origins": [],
    }
    launcher = StubLauncher(storage, "https://github.com/")
    audit = tmp_path / "audit.log"
    result = capture_session(
        _request(audit=audit),
        vault=vault,
        launcher=launcher,
        confirm=lambda _prompt: "",  # bypass interactive prompt
    )
    assert result.entry.host == "github.com"
    assert result.entry.cookies_count == 1
    assert result.vault_path.exists()
    entries = read_audit_log(audit)
    assert any(e.get("event") == "auth.login" for e in entries)
    # Cookie value never appears in the audit log.
    for entry in entries:
        for value in entry.values():
            if isinstance(value, str):
                assert "long-session-value-abc123" not in value


def test_capture_session_rejects_ci_mode(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    launcher = StubLauncher({"cookies": [], "origins": []}, "https://github.com/")
    with pytest.raises(AuthCommandForbiddenInCiError):
        capture_session(_request(ci=True), vault=vault, launcher=launcher)


def test_capture_session_rejects_cross_origin_redirect(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    storage: dict[str, Any] = {"cookies": [], "origins": []}
    launcher = StubLauncher(storage, "https://attacker.example/")
    with pytest.raises(LoginOriginChangedError) as info:
        capture_session(
            _request(allowed=("github.com",)),
            vault=vault,
            launcher=launcher,
            confirm=lambda _prompt: "",
        )
    assert info.value.code == "E-AUTH-005"


def test_capture_session_allows_known_idp_redirect(tmp_path: Path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    storage = {
        "cookies": [{"name": "s", "value": "x" * 20, "domain": "github.com"}],
        "origins": [],
    }
    launcher = StubLauncher(storage, "https://accounts.google.com/CheckCookie")
    # Operator added the IdP host to the allowlist.
    result = capture_session(
        _request(allowed=("github.com", "accounts.google.com")),
        vault=vault,
        launcher=launcher,
        confirm=lambda _prompt: "",
    )
    assert result.landed_url.startswith("https://accounts.google.com/")


def test_host_pair_from_login_url_defaults_to_url_host() -> None:
    assert host_pair_from_login_url("https://github.com/login", None) == "github.com"
    assert host_pair_from_login_url("https://github.com/login", "GITHUB.com") == "github.com"


def test_host_pair_from_login_url_rejects_missing_host() -> None:
    with pytest.raises(ValueError):
        host_pair_from_login_url("not-a-url", None)


def test_hosts_iterable_deduplicates_and_lowercases() -> None:
    assert hosts_iterable("Example.com", ["Example.com", "other.com"]) == (
        "example.com",
        "other.com",
    )


def test_banner_mentions_credentials_never_seen_by_sentinel() -> None:
    text = _banner("https://example.com/login", resolve_profile("github-oauth"))
    assert "NEVER" in text
    assert "github-oauth" in text or "GitHub OAuth" in text
