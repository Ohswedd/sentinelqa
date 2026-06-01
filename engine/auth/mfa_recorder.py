# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""2FA / WebAuthn flow recorder (v1.3.0).

The existing auth profiles cover OAuth and form login. The next step
up is multi-factor: TOTP (Google Authenticator etc.) and WebAuthn
(Yubikey, Touch ID, Face ID). Both require state that lives outside
the browser session.

This module owns the **detection + scripting** layer:

* :func:`detect_mfa_kind` — look at a captured login page (HTML) and
  decide whether a TOTP or WebAuthn prompt is rendered.
* :func:`compute_totp` — generate the current 6-digit TOTP for a
  given base32 secret (RFC 6238).
* :class:`WebAuthnVirtualAuthenticator` — declarative spec for the
  Chrome DevTools Virtual Authenticator the runner will instantiate.

The runner-side Playwright code (lives outside this module) consumes
these helpers to drive the browser through the MFA step.
"""

from __future__ import annotations

import base64
import hmac
import re
import struct
import time
from dataclasses import dataclass
from typing import Final, Literal

MfaKind = Literal["none", "totp", "webauthn", "sms", "email_code"]


@dataclass(frozen=True, slots=True)
class MfaDetectionResult:
    kind: MfaKind
    selector_hint: str | None = None
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class WebAuthnVirtualAuthenticator:
    """Spec for Playwright's Chrome DevTools virtual authenticator.

    The runner calls ``CDPSession.send('WebAuthn.addVirtualAuthenticator', spec)``
    with this dict so the test environment can sign challenges without
    a physical key.
    """

    protocol: Literal["ctap1/u2f", "ctap2", "u2f", "ctap2_1"] = "ctap2"
    transport: Literal["usb", "nfc", "ble", "internal"] = "internal"
    has_resident_key: bool = True
    has_user_verification: bool = True
    is_user_verified: bool = True
    automatic_presence_simulation: bool = True

    def to_cdp_dict(self) -> dict[str, object]:
        return {
            "options": {
                "protocol": self.protocol,
                "transport": self.transport,
                "hasResidentKey": self.has_resident_key,
                "hasUserVerification": self.has_user_verification,
                "isUserVerified": self.is_user_verified,
                "automaticPresenceSimulation": self.automatic_presence_simulation,
            }
        }


# --------------------------------------------------------------------------- #
# MFA detection — pure HTML inspection
# --------------------------------------------------------------------------- #


_TOTP_HINTS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bauthenticator app\b", re.IGNORECASE),
    re.compile(r"\b(?:6-?digit|six-?digit)\s+code\b", re.IGNORECASE),
    re.compile(r"\bone[- ]time (?:password|code)\b", re.IGNORECASE),
    re.compile(r"\bTOTP\b"),
    re.compile(r"<input\b[^>]+(?:autocomplete\s*=\s*['\"]one-time-code['\"])", re.IGNORECASE),
)
_WEBAUTHN_HINTS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:security key|hardware key|passkey)\b", re.IGNORECASE),
    re.compile(r"\bUse (?:Touch ID|Face ID|Windows Hello)\b", re.IGNORECASE),
    re.compile(r"navigator\.credentials\.get"),
    re.compile(r"PublicKeyCredential"),
)
_SMS_HINTS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:texted|sent).+\b(?:phone|mobile)\b", re.IGNORECASE),
    re.compile(r"\bSMS code\b", re.IGNORECASE),
    re.compile(r"\bcode.+\bto your (?:phone|mobile)\b", re.IGNORECASE),
)
_EMAIL_HINTS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bcheck your email\b", re.IGNORECASE),
    re.compile(r"\b(?:email|magic) link\b", re.IGNORECASE),
)


def detect_mfa_kind(html: str) -> MfaDetectionResult:
    """Inspect a login-page HTML payload and classify the MFA challenge.

    Order matters: WebAuthn first (most specific), then SMS / email
    (look for delivery-channel words first), and only then TOTP
    (whose "6-digit code" phrase otherwise eats SMS / email flows).
    """

    for pattern in _WEBAUTHN_HINTS:
        if pattern.search(html):
            return MfaDetectionResult(
                kind="webauthn",
                selector_hint="passkey/security-key prompt",
                rationale=f"Matched {pattern.pattern!r}",
            )
    for pattern in _SMS_HINTS:
        if pattern.search(html):
            return MfaDetectionResult(
                kind="sms",
                selector_hint="sms-code input",
                rationale=f"Matched {pattern.pattern!r}",
            )
    for pattern in _EMAIL_HINTS:
        if pattern.search(html):
            return MfaDetectionResult(
                kind="email_code",
                selector_hint="email-code input",
                rationale=f"Matched {pattern.pattern!r}",
            )
    for pattern in _TOTP_HINTS:
        if pattern.search(html):
            return MfaDetectionResult(
                kind="totp",
                selector_hint='input[autocomplete="one-time-code"]',
                rationale=f"Matched {pattern.pattern!r}",
            )
    return MfaDetectionResult(kind="none")


# --------------------------------------------------------------------------- #
# TOTP — RFC 6238
# --------------------------------------------------------------------------- #


def compute_totp(
    secret_base32: str,
    *,
    timestamp: float | None = None,
    interval: int = 30,
    digits: int = 6,
) -> str:
    """Return the current TOTP for a base32 secret per RFC 6238.

    The default 30-second interval and 6 digits match every
    consumer-grade authenticator app. ``timestamp`` is overridable
    for deterministic tests.
    """

    secret = base64.b32decode(_normalise_base32(secret_base32), casefold=True)
    counter = int((timestamp if timestamp is not None else time.time()) // interval)
    counter_bytes = struct.pack(">Q", counter)
    digest = hmac.new(secret, counter_bytes, "sha1").digest()
    offset = digest[-1] & 0x0F
    code_int = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    return str(code_int % (10**digits)).zfill(digits)


def _normalise_base32(secret: str) -> str:
    """Strip spaces and pad to a multiple of 8 chars."""

    cleaned = secret.upper().replace(" ", "").replace("-", "")
    remainder = len(cleaned) % 8
    if remainder:
        cleaned += "=" * (8 - remainder)
    return cleaned


# --------------------------------------------------------------------------- #
# Recorder data class — a small DSL the runner walks
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class MfaScript:
    """The step list the runner replays after the password step.

    Each step is one of:
    - ``("fill", selector, value)`` → fill a text input.
    - ``("click", selector, "")`` → click a button.
    - ``("webauthn", "register", spec_json)`` → add the virtual
      authenticator described by ``spec_json``.
    - ``("wait", "selector_or_url", timeout_ms_as_str)`` → wait for
      the locator to appear (or the URL to change).
    """

    steps: tuple[tuple[str, str, str], ...]
    detection: MfaDetectionResult


def build_totp_script(*, secret_base32: str, code_selector: str, submit_selector: str) -> MfaScript:
    code = compute_totp(secret_base32)
    return MfaScript(
        steps=(
            ("fill", code_selector, code),
            ("click", submit_selector, ""),
            ("wait", "domcontentloaded", "30000"),
        ),
        detection=MfaDetectionResult(kind="totp"),
    )


def build_webauthn_script(spec: WebAuthnVirtualAuthenticator | None = None) -> MfaScript:
    spec = spec or WebAuthnVirtualAuthenticator()
    import json

    return MfaScript(
        steps=(
            ("webauthn", "register", json.dumps(spec.to_cdp_dict())),
            ("wait", "domcontentloaded", "30000"),
        ),
        detection=MfaDetectionResult(kind="webauthn"),
    )


__all__ = [
    "MfaDetectionResult",
    "MfaKind",
    "MfaScript",
    "WebAuthnVirtualAuthenticator",
    "build_totp_script",
    "build_webauthn_script",
    "compute_totp",
    "detect_mfa_kind",
]
