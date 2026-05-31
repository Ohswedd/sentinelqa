"""Phase 31 — ``auth.strategy: browser_session`` validation rules."""

from __future__ import annotations

import pytest
from engine.config.schema import AuthConfig
from pydantic import ValidationError


def test_browser_session_requires_session_name() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(strategy="browser_session")


def test_browser_session_accepts_session_name() -> None:
    cfg = AuthConfig(strategy="browser_session", session_name="github-myorg")
    assert cfg.session_name == "github-myorg"


def test_session_name_without_browser_session_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(strategy="test_user", session_name="github-myorg")


def test_existing_strategies_still_load() -> None:
    AuthConfig(strategy="test_user")
    AuthConfig(strategy="api_key")
    AuthConfig(strategy="oauth")
    AuthConfig(strategy="none")
