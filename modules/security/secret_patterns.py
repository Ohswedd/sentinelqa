"""Detection-mode secret patterns (Phase 13.08).

The Phase 01 redaction layer (``engine.policy.redaction``) is built for
*redaction* (replace the secret with ``[REDACTED:<cat>]`` before it
leaves the process). The Phase 13 frontend-secrets check needs the
opposite shape: scan a corpus and return a list of matches with
locations so they can become :class:`SecurityIssue` records.

This module exposes a curated regex catalog plus :func:`scan_for_secrets`
which returns a tuple of redacted matches. To avoid leaking the secret
back through the finding payload we ONLY persist the secret category,
match location, and a one-character-redacted preview (first 4 chars +
``…`` for context).

CLAUDE §33: the source text itself never goes to a log or report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# --- Regex helpers ---------------------------------------------------

# JWT: three base64url groups separated by '.', length-bounded to reject
# trivially short matches that show up in tutorials.
_JWT_RE: Final[re.Pattern[str]] = re.compile(
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
)

# AWS access key (AKIA + 16 base32). Stable for ~15 years.
_AWS_AK_RE: Final[re.Pattern[str]] = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
# AWS temp creds (ASIA + 16 base32).
_AWS_ASIA_RE: Final[re.Pattern[str]] = re.compile(r"\bASIA[0-9A-Z]{16}\b")
# AWS secret access key (base64-ish, 40 chars). Higher false-positive
# rate than the access-key id, so we only flag it when paired with one.
# (Reserved for future bundle scanning.)

# Generic high-entropy key/api/secret patterns. We match the assignment
# shape rather than free-floating bytes to keep the false-positive rate
# in check.
_GENERIC_API_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?:
        api[-_]?key
      | apikey
      | x[-_]?api[-_]?key
      | client[-_]?secret
      | secret[-_]?key
      | access[-_]?token
      | bearer[-_]?token
    )
    \s* [:=] \s*
    ['"]?
    (?P<value>[A-Za-z0-9_\-]{24,200})
    ['"]?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_GOOGLE_API_RE: Final[re.Pattern[str]] = re.compile(r"\bAIza[0-9A-Za-z_\-]{30,40}\b")
_STRIPE_LIVE_RE: Final[re.Pattern[str]] = re.compile(r"\bsk_live_[0-9A-Za-z]{16,}\b")
_GITHUB_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\bghp_[0-9A-Za-z]{30,}\b")

_PRIVATE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"
)


@dataclass(frozen=True, slots=True)
class SecretMatch:
    """One detected secret-like substring.

    ``preview`` is a deliberately short, partially-masked snippet (e.g.
    ``"AKIA…"``) so the finding can identify the kind of secret without
    leaking its value.
    """

    category: str
    preview: str
    offset: int
    length: int


_PREVIEW_HEAD: Final[int] = 4


def _preview(value: str) -> str:
    head = value[:_PREVIEW_HEAD]
    return f"{head}…" if value else "…"


def scan_for_secrets(text: str) -> tuple[SecretMatch, ...]:
    """Return matches without ever surfacing the secret value itself.

    ``text`` can be a JS bundle, a DOM snapshot, a localStorage dump,
    etc. Empty / unparseable input returns an empty tuple.
    """

    if not text:
        return ()

    found: list[SecretMatch] = []

    def _add(category: str, value: str, offset: int) -> None:
        if not value:
            return
        found.append(
            SecretMatch(
                category=category,
                preview=_preview(value),
                offset=offset,
                length=len(value),
            )
        )

    for m in _JWT_RE.finditer(text):
        _add("jwt", m.group(0), m.start())
    for m in _AWS_AK_RE.finditer(text):
        _add("aws_access_key_id", m.group(0), m.start())
    for m in _AWS_ASIA_RE.finditer(text):
        _add("aws_session_credential", m.group(0), m.start())
    for m in _GOOGLE_API_RE.finditer(text):
        _add("google_api_key", m.group(0), m.start())
    for m in _STRIPE_LIVE_RE.finditer(text):
        _add("stripe_live_key", m.group(0), m.start())
    for m in _GITHUB_TOKEN_RE.finditer(text):
        _add("github_token", m.group(0), m.start())
    for m in _PRIVATE_KEY_RE.finditer(text):
        _add("private_key_block", m.group(0), m.start())
    for m in _GENERIC_API_KEY_RE.finditer(text):
        value = m.group("value")
        # Filter low-entropy values such as ``CHANGEME``, ``yourkey``.
        if _looks_low_entropy(value):
            continue
        _add("generic_api_key", value, m.start("value"))

    # Stable order: offset, then category, so output is deterministic.
    found.sort(key=lambda s: (s.offset, s.category))
    return tuple(found)


_LOW_ENTROPY_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "changeme",
        "secret",
        "yourkey",
        "yourapikey",
        "todo",
        "placeholder",
        "xxxxxxxx",
        "redacted",
    }
)


def _looks_low_entropy(value: str) -> bool:
    norm = value.lower()
    if norm in _LOW_ENTROPY_TOKENS:
        return True
    distinct = len(set(value))
    return distinct <= 4


# --- PII (anonymous-only) -------------------------------------------

_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
_PHONE_RE: Final[re.Pattern[str]] = re.compile(r"\+?\d[\d\s().\-]{8,}\d")


@dataclass(frozen=True, slots=True)
class PiiMatch:
    category: str
    preview: str
    offset: int


def scan_for_pii(text: str) -> tuple[PiiMatch, ...]:
    """Return PII-shaped matches (emails, phone-ish digit strings).

    We mask everything except the trailing 2 chars of the local part
    (emails) or the last 4 digits (phones) so the finding pinpoints the
    shape without leaking the value.
    """

    if not text:
        return ()
    found: list[PiiMatch] = []
    for m in _EMAIL_RE.finditer(text):
        addr = m.group(0)
        local, _, domain = addr.partition("@")
        masked = ("*" * max(1, len(local) - 2)) + local[-2:] if local else "*"
        found.append(PiiMatch(category="email", preview=f"{masked}@{domain}", offset=m.start()))
    for m in _PHONE_RE.finditer(text):
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 10:
            continue
        masked = "*" * (len(digits) - 4) + digits[-4:]
        found.append(PiiMatch(category="phone", preview=masked, offset=m.start()))
    found.sort(key=lambda p: (p.offset, p.category))
    return tuple(found)


__all__ = [
    "SecretMatch",
    "PiiMatch",
    "scan_for_secrets",
    "scan_for_pii",
]
