"""Forbidden capability registry (our engineering rules, the documentation).

Any plugin/module that tries to register one of these capability strings at
runtime is rejected immediately. The plugin loader will consult
this set; until then, the constant is here so other code can refer to it
and so the safety-boundary tests have a concrete surface to assert against.
"""

from __future__ import annotations

from typing import Final

from engine.errors.base import ForbiddenFlagError

FORBIDDEN_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        "bot_detection_bypass",
        "captcha_bypass",
        "captcha_solving",
        "stealth_automation",
        "fingerprint_evasion",
        "fingerprint_spoofing",
        "credential_stuffing",
        "session_theft",
        "cookie_theft",
        "data_exfiltration",
        "spam_automation",
        "platform_manipulation",
        "phishing",
        "proxy_rotation_for_evasion",
        "rate_limit_bypass",
        "unauthorized_exploit",
        "destructive_against_public",
        "undetectable_mode",
    }
)


FORBIDDEN_CLI_FLAGS: Final[frozenset[str]] = frozenset(
    {
        "--stealth",
        "--evade",
        "--evasion",
        "--bypass",
        "--bypass-captcha",
        "--bypass-rate-limit",
        "--undetectable",
        "--rotate-proxies",
        "--spoof-fingerprint",
    }
)


def assert_capability_allowed(capability: str) -> None:
    """Raise :class:`ForbiddenFlagError` if ``capability`` is on the deny list."""

    if capability in FORBIDDEN_CAPABILITIES:
        raise ForbiddenFlagError(
            flag=capability,
            technical_context={"capability": capability},
        )


def assert_flag_allowed(flag: str) -> None:
    """Raise :class:`ForbiddenFlagError` if ``flag`` is on the deny list."""

    if flag in FORBIDDEN_CLI_FLAGS:
        raise ForbiddenFlagError(
            flag=flag,
            technical_context={"cli_flag": flag},
        )


__all__ = [
    "FORBIDDEN_CAPABILITIES",
    "FORBIDDEN_CLI_FLAGS",
    "assert_capability_allowed",
    "assert_flag_allowed",
]
