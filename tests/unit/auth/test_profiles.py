"""Built-in auth profiles + the credential-name lint guard."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest
from engine.auth import AuthProfile, list_profiles, resolve_profile
from engine.auth.profiles import ProfileNotFoundError

KNOWN_OAUTH = {"google-oauth", "github-oauth", "microsoft-entra"}
KNOWN_LLM_WEB = {
    "claude-ai",
    "chatgpt-web",
    "chatgpt-codex",
    "google-gemini",
    "mistral-le-chat",
}


def test_every_built_in_profile_loads() -> None:
    profiles = list_profiles()
    assert {p.name for p in profiles} == KNOWN_OAUTH | KNOWN_LLM_WEB


@pytest.mark.parametrize(
    "profile_name",
    sorted(KNOWN_OAUTH | KNOWN_LLM_WEB),
)
def test_profile_urls_are_https_and_have_hosts(profile_name: str) -> None:
    profile = resolve_profile(profile_name)
    for url in (
        profile.login_url_pattern,
        profile.tos_url,
        *profile.success_url_patterns,
    ):
        parsed = urlparse(url)
        assert parsed.scheme == "https", f"{url} is not HTTPS"
        assert parsed.hostname, f"{url} has no host"


def test_profile_category_is_oauth_or_llm_web() -> None:
    for profile in list_profiles():
        assert profile.category in {"oauth", "llm-web"}


def test_resolve_profile_unknown_raises() -> None:
    with pytest.raises(ProfileNotFoundError):
        resolve_profile("does-not-exist")


def test_profile_construction_rejects_http() -> None:
    with pytest.raises(ValueError):
        AuthProfile(
            name="x",
            label="x",
            login_url_pattern="http://insecure.example.com/",
            success_url_patterns=("https://insecure.example.com/",),
            mfa_hint="",
            tos_url="https://insecure.example.com/tos",
            category="oauth",
        )


def test_profile_construction_requires_at_least_one_success_pattern() -> None:
    with pytest.raises(ValueError):
        AuthProfile(
            name="x",
            label="x",
            login_url_pattern="https://example.com/login",
            success_url_patterns=(),
            mfa_hint="",
            tos_url="https://example.com/tos",
            category="oauth",
        )


def test_profile_construction_rejects_bad_category() -> None:
    with pytest.raises(ValueError):
        AuthProfile(
            name="x",
            label="x",
            login_url_pattern="https://example.com/login",
            success_url_patterns=("https://example.com/",),
            mfa_hint="",
            tos_url="https://example.com/tos",
            category="unknown",
        )
