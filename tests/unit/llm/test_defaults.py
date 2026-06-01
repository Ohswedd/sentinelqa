# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the local-LLM default resolver."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest
from engine.llm import defaults
from engine.llm.defaults import (
    OLLAMA_DISABLED_ENV_VAR,
    OLLAMA_HOST_ENV_VAR,
    PROVIDER_ENV_VAR,
    reset_cache,
    resolve_default_provider,
)


@pytest.fixture(autouse=True)
def _reset_probe_cache():
    reset_cache()
    yield
    reset_cache()


def test_explicit_requested_provider_is_returned_unchanged() -> None:
    result = resolve_default_provider(requested="anthropic", env={}, probe=False)
    assert result.name == "anthropic"
    assert "explicit" in result.reason


def test_provider_env_var_wins_over_cloud_keys() -> None:
    env = {
        PROVIDER_ENV_VAR: "openai",
        "ANTHROPIC_API_KEY": "sk-...",
    }
    result = resolve_default_provider(env=env, probe=False)
    assert result.name == "openai"


def test_anthropic_key_picks_anthropic() -> None:
    env = {"ANTHROPIC_API_KEY": "sk-ant-..."}
    result = resolve_default_provider(env=env, probe=False)
    assert result.name == "anthropic"


def test_openai_key_picks_openai() -> None:
    env = {"OPENAI_API_KEY": "sk-..."}
    result = resolve_default_provider(env=env, probe=False)
    assert result.name == "openai"


def test_gemini_key_picks_gemini() -> None:
    result = resolve_default_provider(env={"GEMINI_API_KEY": "x"}, probe=False)
    assert result.name == "gemini"


def test_google_api_key_aliases_gemini() -> None:
    result = resolve_default_provider(env={"GOOGLE_API_KEY": "x"}, probe=False)
    assert result.name == "gemini"


def test_empty_env_falls_back_to_null_without_probe() -> None:
    result = resolve_default_provider(env={}, probe=False)
    assert result.name == "null"
    assert "Ollama" in result.reason


def test_disabled_local_llm_returns_null_even_when_ollama_reachable() -> None:
    env = {OLLAMA_DISABLED_ENV_VAR: "1"}
    with patch.object(defaults, "_ollama_reachable", return_value=True):
        result = resolve_default_provider(env=env, probe=True)
    assert result.name == "null"
    assert "opt-out" in result.reason


def test_ollama_reachable_picks_ollama() -> None:
    with patch.object(defaults, "_ollama_reachable", return_value=True):
        result = resolve_default_provider(env={}, probe=True)
    assert result.name == "ollama"
    assert "Ollama" in result.reason


def test_ollama_unreachable_falls_back_to_null() -> None:
    with patch.object(defaults, "_ollama_reachable", return_value=False):
        result = resolve_default_provider(env={}, probe=True)
    assert result.name == "null"


def test_ollama_host_env_var_is_honoured() -> None:
    """When OLLAMA_HOST is set the probe targets the custom endpoint."""

    captured: list[str] = []

    def fake_reachable(host: str) -> bool:
        captured.append(host)
        return True

    with patch.object(defaults, "_ollama_reachable", side_effect=fake_reachable):
        resolve_default_provider(env={OLLAMA_HOST_ENV_VAR: "http://my-box:11434"}, probe=True)
    assert captured == ["http://my-box:11434"]


def test_reachable_probe_caches_result() -> None:
    """Calling resolve twice triggers one probe."""

    call_count = {"n": 0}

    def fake_create_connection(*args, **kwargs):
        call_count["n"] += 1
        raise OSError("no ollama")

    with patch.object(socket, "create_connection", side_effect=fake_create_connection):
        first = defaults._ollama_reachable("http://localhost:11434")
        second = defaults._ollama_reachable("http://localhost:11434")
    assert first is False
    assert second is False
    assert call_count["n"] == 1


def test_reachable_probe_handles_invalid_url() -> None:
    """Malformed inputs must not raise — they degrade to a bool."""

    with patch.object(socket, "create_connection", side_effect=OSError("nope")):
        result = defaults._ollama_reachable("not-a-url")
    assert result is False
