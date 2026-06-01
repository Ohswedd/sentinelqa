# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Local-LLM default resolution (v1.4.0).

Before v1.4.0 callers had to pick a provider explicitly. Without an
API key the only working option was ``"null"`` — degrading every
LLM-driven check silently. The right default for a
privacy-conscious user is to detect a running local Ollama and use
it; otherwise return the null provider so the lifecycle keeps
working.

Resolution order (the first match wins):

1. The caller already picked a provider — return it untouched.
2. An environment variable (``SENTINELQA_LLM_PROVIDER``) names one.
3. A cloud provider's canonical API-key env-var is set
   (``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``, ``GEMINI_API_KEY``).
4. The local Ollama HTTP endpoint responds to a one-shot ``GET /``
   within a short timeout — return the ``ollama`` provider.
5. Fall back to the null provider.

The Ollama probe is intentionally cheap: a single ``GET`` with a
short timeout, no model load. We re-probe at most once per process
(cached via :func:`_ollama_reachable`); tests reset the cache via
:func:`reset_cache`.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

from engine.llm.registry import resolve_provider

# Environment variables we consult.
PROVIDER_ENV_VAR: Final[str] = "SENTINELQA_LLM_PROVIDER"
OLLAMA_HOST_ENV_VAR: Final[str] = "OLLAMA_HOST"
OLLAMA_DISABLED_ENV_VAR: Final[str] = "SENTINELQA_DISABLE_LOCAL_LLM"

# Cloud provider env-var → provider name. When one of these env-vars
# is set, we prefer the corresponding cloud provider over Ollama —
# the user explicitly configured a paid account.
_CLOUD_KEY_TO_PROVIDER: Final[dict[str, str]] = {
    "ANTHROPIC_API_KEY": "anthropic",
    "OPENAI_API_KEY": "openai",
    "GEMINI_API_KEY": "gemini",
    "GOOGLE_API_KEY": "gemini",
    "MISTRAL_API_KEY": "mistral",
    "GROQ_API_KEY": "groq",
    "OPENROUTER_API_KEY": "openrouter",
}

DEFAULT_OLLAMA_HOST: Final[str] = "http://localhost:11434"
_PROBE_TIMEOUT_SECONDS: Final[float] = 0.35

# Probe cache. ``None`` = not yet probed; bool otherwise.
_OLLAMA_REACHABLE_CACHE: bool | None = None


@dataclass(frozen=True, slots=True)
class ResolvedProvider:
    """The provider chosen + the reason we chose it."""

    name: str
    reason: str


def reset_cache() -> None:
    """Forget the cached Ollama probe result. Test helper."""

    global _OLLAMA_REACHABLE_CACHE
    _OLLAMA_REACHABLE_CACHE = None


def ollama_host() -> str:
    """Return the configured Ollama host."""

    return os.environ.get(OLLAMA_HOST_ENV_VAR, DEFAULT_OLLAMA_HOST)


def _ollama_reachable(host: str) -> bool:
    """Cheap TCP probe — does anything respond on the Ollama port?"""

    global _OLLAMA_REACHABLE_CACHE
    if _OLLAMA_REACHABLE_CACHE is not None:
        return _OLLAMA_REACHABLE_CACHE

    parsed = urlparse(host)
    hostname = parsed.hostname or "localhost"
    port = parsed.port or (11434 if parsed.scheme in ("http", "") else 443)
    try:
        with socket.create_connection((hostname, port), timeout=_PROBE_TIMEOUT_SECONDS):
            _OLLAMA_REACHABLE_CACHE = True
            return True
    except (OSError, ValueError):
        _OLLAMA_REACHABLE_CACHE = False
        return False


def resolve_default_provider(
    *,
    requested: str | None = None,
    env: dict[str, str] | None = None,
    probe: bool = True,
) -> ResolvedProvider:
    """Pick a provider when the caller has not explicitly configured one.

    Parameters
    ----------
    requested:
        The caller's chosen provider name (or ``None``). When set,
        returned untouched — callers that already know what they want
        bypass every default.
    env:
        Environment-variable mapping (defaults to :data:`os.environ`).
        Tests pass a synthetic dict to control resolution.
    probe:
        Whether to TCP-probe the Ollama host. Tests disable this when
        they only want the env-var fallback path.
    """

    if requested:
        return ResolvedProvider(name=requested, reason="explicit caller choice")

    env_map = env if env is not None else dict(os.environ)

    pinned = env_map.get(PROVIDER_ENV_VAR, "").strip().lower()
    if pinned:
        return ResolvedProvider(name=pinned, reason=f"{PROVIDER_ENV_VAR} env var")

    for key, provider_name in _CLOUD_KEY_TO_PROVIDER.items():
        if env_map.get(key, "").strip():
            return ResolvedProvider(name=provider_name, reason=f"{key} env var set")

    if env_map.get(OLLAMA_DISABLED_ENV_VAR, "").strip().lower() in ("1", "true", "yes"):
        return ResolvedProvider(name="null", reason=f"{OLLAMA_DISABLED_ENV_VAR} forced opt-out")

    host = env_map.get(OLLAMA_HOST_ENV_VAR, DEFAULT_OLLAMA_HOST)
    if probe and _ollama_reachable(host):
        return ResolvedProvider(name="ollama", reason=f"local Ollama reachable at {host}")

    return ResolvedProvider(name="null", reason="no provider configured and Ollama unreachable")


def get_default_provider(
    *,
    requested: str | None = None,
    env: dict[str, str] | None = None,
    probe: bool = True,
):
    """Resolve + instantiate the default provider in one call."""

    resolved = resolve_default_provider(requested=requested, env=env, probe=probe)
    return resolve_provider(resolved.name)


__all__ = [
    "DEFAULT_OLLAMA_HOST",
    "OLLAMA_DISABLED_ENV_VAR",
    "OLLAMA_HOST_ENV_VAR",
    "PROVIDER_ENV_VAR",
    "ResolvedProvider",
    "get_default_provider",
    "ollama_host",
    "reset_cache",
    "resolve_default_provider",
]
