"""LLM-web profile coverage — names, hosts, ToS links."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest
from engine.auth import resolve_profile

EXPECTED_HOSTS = {
    "claude-ai": "claude.ai",
    "chatgpt-web": "chatgpt.com",
    "chatgpt-codex": "chatgpt.com",
    "google-gemini": "gemini.google.com",
    "mistral-le-chat": "chat.mistral.ai",
}

EXPECTED_TOS_HOSTS = {
    "claude-ai": "www.anthropic.com",
    "chatgpt-web": "openai.com",
    "chatgpt-codex": "openai.com",
    "google-gemini": "policies.google.com",
    "mistral-le-chat": "mistral.ai",
}


@pytest.mark.parametrize("name,expected_host", sorted(EXPECTED_HOSTS.items()))
def test_login_url_resolves_to_expected_host(name: str, expected_host: str) -> None:
    profile = resolve_profile(name)
    parsed = urlparse(profile.login_url_pattern)
    assert parsed.hostname == expected_host


@pytest.mark.parametrize("name,expected_tos_host", sorted(EXPECTED_TOS_HOSTS.items()))
def test_tos_url_resolves_to_provider_domain(name: str, expected_tos_host: str) -> None:
    profile = resolve_profile(name)
    parsed = urlparse(profile.tos_url)
    assert parsed.hostname == expected_tos_host
    assert parsed.scheme == "https"


@pytest.mark.parametrize("name", sorted(EXPECTED_HOSTS))
def test_success_url_patterns_are_non_empty_https(name: str) -> None:
    profile = resolve_profile(name)
    assert profile.success_url_patterns
    for pat in profile.success_url_patterns:
        parsed = urlparse(pat)
        assert parsed.scheme == "https"
        assert parsed.hostname
