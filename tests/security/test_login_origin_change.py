"""Login flow refuses to capture across an unexpected cross-origin redirect."""

from __future__ import annotations

from typing import Any

import pytest
from engine.auth import LoginRequest, Vault, capture_session
from engine.errors.base import LoginOriginChangedError

from tests.unit.auth.test_vault_crypto import StubKeyStore


class RedirectLauncher:
    def __init__(self, landed_url: str) -> None:
        self._landed = landed_url

    def capture(self, *, login_url: str, browser: str, confirm: Any) -> tuple[dict[str, Any], str]:
        return {"cookies": [], "origins": []}, self._landed


def _request(allowed: tuple[str, ...]) -> LoginRequest:
    return LoginRequest(
        name="ok",
        login_url="https://github.com/login",
        target_host="github.com",
        allowed_hosts=allowed,
        profile=None,
        browser="chromium",
        ttl_hours=24,
        force=False,
        ci=False,
    )


def test_redirect_to_unrelated_host_refused(tmp_path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    with pytest.raises(LoginOriginChangedError) as info:
        capture_session(
            _request(allowed=("github.com",)),
            vault=vault,
            launcher=RedirectLauncher("https://phishing.example/oauth"),
            confirm=lambda _p: "",
        )
    assert info.value.code == "E-AUTH-005"


def test_redirect_to_allowlisted_idp_allowed(tmp_path) -> None:
    vault = Vault(root=tmp_path, key_store=StubKeyStore())
    capture_session(
        _request(allowed=("github.com", "login.microsoftonline.com")),
        vault=vault,
        launcher=RedirectLauncher("https://login.microsoftonline.com/oauth/done"),
        confirm=lambda _p: "",
    )
    assert vault.has("github.com", "ok")
