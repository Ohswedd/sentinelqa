"""Redaction primitives (CLAUDE.md §33, PRD §20, §23.1).

Every log line, audit entry, finding payload, and agent message passes
through :func:`redact` (or :func:`redact_headers` / :func:`redact_url`)
before leaving the process. The function recursively walks strings,
dicts, lists, and tuples; matches are replaced with ``[REDACTED:<cat>]``
markers so downstream consumers can still see *that* a secret was present
without seeing its value.

Performance contract: a 5 MB JSON document redacts in under one second on
a modest developer laptop (see `tests/unit/policy/test_redaction_perf.py`).

Caller-controlled allowlists live on :data:`_LOCAL_OVERRIDE`; tests and
power-users opt in by calling :func:`add_allowlist_token` for the lifetime
of the current process. CI never enables an allowlist by default.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, Final, cast
from urllib.parse import parse_qsl, quote, urlparse, urlunparse

_REDACTED_TEMPLATE: Final[str] = "[REDACTED:{category}]"


@dataclass(frozen=True, slots=True)
class RedactionRule:
    """Named regex rule.

    ``pattern`` matches the secret *value* (not the surrounding context).
    When a match is found, the matched substring is replaced wholesale with
    ``[REDACTED:<category>]``.
    """

    category: str
    pattern: re.Pattern[str]
    description: str


# ---------------------------------------------------------------------------
# Key-name rules. Triggered when a dict's *key* signals "this is a secret".
# Triggers replacement of the entire value (string-coerced).
# ---------------------------------------------------------------------------
SECRET_KEY_NAMES: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "auth_token",
        "session_token",
        "session_id",
        "sessionid",
        "csrf_token",
        "xsrf_token",
        "cookie",
        "set_cookie",
        "set-cookie",
        "authorization",
        "proxy_authorization",
        "proxy-authorization",
        "api_key",
        "apikey",
        "api-key",
        "x_api_key",
        "x-api-key",
        "x_auth_token",
        "x-auth-token",
        "client_secret",
        "private_key",
        "privatekey",
        "rsa_private_key",
        "ssh_key",
        "service_account_key",
    }
)


def _key_category(key: str) -> str | None:
    """Return the category label for a sensitive key, or None."""

    lowered = key.lower().replace("-", "_")
    if lowered in SECRET_KEY_NAMES:
        return _CATEGORY_FOR_KEY.get(lowered, "secret_field")
    return None


_CATEGORY_FOR_KEY: Final[dict[str, str]] = {
    "password": "password",
    "passwd": "password",
    "pwd": "password",
    "secret": "secret_field",
    "token": "token",
    "access_token": "access_token",
    "refresh_token": "refresh_token",
    "id_token": "id_token",
    "auth_token": "auth_token",
    "session_token": "session_id",
    "session_id": "session_id",
    "sessionid": "session_id",
    "csrf_token": "csrf_token",
    "xsrf_token": "csrf_token",
    "cookie": "cookie",
    "set_cookie": "cookie",
    "set-cookie": "cookie",
    "authorization": "authorization",
    "proxy_authorization": "authorization",
    "proxy-authorization": "authorization",
    "api_key": "api_key",
    "apikey": "api_key",
    "api-key": "api_key",
    "x_api_key": "api_key",
    "x-api-key": "api_key",
    "x_auth_token": "auth_token",
    "x-auth-token": "auth_token",
    "client_secret": "client_secret",
    "private_key": "private_key",
    "privatekey": "private_key",
    "rsa_private_key": "private_key",
    "ssh_key": "private_key",
    "service_account_key": "gcp_service_account",
}


# ---------------------------------------------------------------------------
# Value-level rules. Triggered by inspecting the value itself.
# ---------------------------------------------------------------------------
BUILTIN_RULES: Final[tuple[RedactionRule, ...]] = (
    RedactionRule(
        category="bearer_token",
        pattern=re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]{8,}", re.IGNORECASE),
        description="HTTP `Bearer <token>` Authorization values.",
    ),
    RedactionRule(
        category="basic_auth",
        pattern=re.compile(r"Basic\s+[A-Za-z0-9+/=]{8,}", re.IGNORECASE),
        description="HTTP Basic auth header values.",
    ),
    RedactionRule(
        category="jwt",
        pattern=re.compile(r"\beyJ[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\b"),
        description="JSON Web Tokens (three base64url segments).",
    ),
    RedactionRule(
        category="aws_access_key_id",
        pattern=re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA)[A-Z0-9]{16}\b"),
        description="AWS access-key IDs.",
    ),
    RedactionRule(
        category="aws_secret_access_key",
        pattern=re.compile(r"(?i)aws(.{0,20})?(secret|key)(.{0,20})?[:=]\s*[A-Za-z0-9/+=]{40}"),
        description="AWS secret access keys in key=value pairs.",
    ),
    RedactionRule(
        category="gcp_service_account",
        pattern=re.compile(
            r'"type"\s*:\s*"service_account"',
        ),
        description="GCP service-account JSON marker; redacts the whole match.",
    ),
    RedactionRule(
        category="openai_or_anthropic_key",
        pattern=re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
        description="Anthropic/OpenAI-style secret keys (`sk-...`).",
    ),
    RedactionRule(
        category="publishable_key",
        pattern=re.compile(r"\bpk-[A-Za-z0-9_\-]{20,}\b"),
        description="Publishable keys with a `pk-` prefix.",
    ),
    RedactionRule(
        category="github_token",
        pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        description="GitHub personal-access / app tokens.",
    ),
    RedactionRule(
        category="slack_token",
        pattern=re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
        description="Slack tokens.",
    ),
    RedactionRule(
        category="private_key",
        pattern=re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        description="PEM-encoded private keys.",
    ),
)


# Per-process false-positive allowlist. Tokens added here will NOT be
# redacted by value-level rules. This exists for legitimate use cases where
# a non-secret string happens to match a permissive rule. We deliberately
# do not read this from config in Phase 01 — CI must never auto-allow.
_LOCAL_OVERRIDE: set[str] = set()


def add_allowlist_token(token: str) -> None:
    """Whitelist ``token`` from value-level redaction for this process."""

    _LOCAL_OVERRIDE.add(token)


def clear_allowlist() -> None:
    """Remove all entries from the local allowlist (used by tests)."""

    _LOCAL_OVERRIDE.clear()


# ---------------------------------------------------------------------------
# Heuristic entropy rule (catches generic high-entropy tokens that none of
# the named rules would catch, e.g. a 40-character random string).
# ---------------------------------------------------------------------------
_GENERIC_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_\-]{32,}")
_ENTROPY_THRESHOLD: Final[float] = 4.0  # bits per char


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(text)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _redact_generic_high_entropy(value: str) -> str:
    """Replace generic high-entropy substrings with a marker."""

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in _LOCAL_OVERRIDE:
            return token
        if _shannon_entropy(token) >= _ENTROPY_THRESHOLD:
            return _REDACTED_TEMPLATE.format(category="high_entropy_token")
        return token

    return _GENERIC_TOKEN_PATTERN.sub(_replace, value)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def _redact_string(value: str) -> str:
    """Apply every value-level rule, then the entropy heuristic."""

    out = value
    for rule in BUILTIN_RULES:
        out = rule.pattern.sub(
            _REDACTED_TEMPLATE.format(category=rule.category),
            out,
        )
    return _redact_generic_high_entropy(out)


def redact(value: Any, *, depth: int = 6) -> Any:
    """Recursively scrub secrets from ``value``.

    ``depth`` caps recursion to defeat pathological inputs (deeply-nested
    dicts/lists). Values past ``depth`` are returned as the literal string
    ``"[REDACTED:depth_limit]"`` so the structural footprint is preserved.

    Tuples are coerced to lists in the output because Pydantic models often
    contain frozen sequences and JSON has no tuple primitive.
    """

    if depth <= 0:
        return _REDACTED_TEMPLATE.format(category="depth_limit")

    if value is None or isinstance(value, bool | int | float):
        return value

    if isinstance(value, str):
        return _redact_string(value)

    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, sub in value.items():
            key_str = str(key)
            category = _key_category(key_str)
            if category is not None and sub is not None and sub != "":
                out[key_str] = _REDACTED_TEMPLATE.format(category=category)
            else:
                out[key_str] = redact(sub, depth=depth - 1)
        return out

    if isinstance(value, list | tuple | set | frozenset):
        return [redact(item, depth=depth - 1) for item in value]

    # Unknown object types fall back to their string representation; we
    # cannot let an opaque object slip through unfiltered.
    return _redact_string(repr(value))


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Case-insensitive HTTP header redaction.

    The set of always-redacted header names is a strict superset of
    :data:`SECRET_KEY_NAMES` to ensure HTTP framing always wins, even when
    a caller's headers dict happens to contain a non-secret-shaped key
    like ``X-API-Key: public-tier``.
    """

    out: dict[str, str] = {}
    always_redact = {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "x-auth-token",
        "x-csrf-token",
        "x-xsrf-token",
    }
    for name, value in headers.items():
        lowered = name.lower()
        if lowered in always_redact:
            out[name] = _REDACTED_TEMPLATE.format(category=lowered)
        else:
            out[name] = _redact_string(value)
    return out


_URL_SECRET_QUERY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "auth_token",
        "session",
        "session_id",
        "sessionid",
        "apikey",
        "api_key",
        "signature",
        "sig",
        "code",
    }
)


def redact_url(url: str) -> str:
    """Strip userinfo from the netloc and redact secret-shaped query params.

    **Cross-language parity note** (Phase 04, ADR-0009, PRD §15.7): the TS
    mirror (``redactUrl`` in ``packages/ts-runtime/src/redact.ts``)
    canonicalises the hostname to lower case via the WHATWG ``URL`` API,
    while ``urlparse`` preserves the original hostname case. The two
    implementations therefore cannot produce byte-identical output for
    arbitrary URLs. The contract is **behavioural**: userinfo is stripped
    on both sides, secret-shaped query keys are replaced with
    ``[REDACTED:url_token]``, and non-secret query values still pass
    through the value-level redactor. Cross-language consumers that need
    to *compare* URLs must normalise hostname case + query order before
    comparison.
    """

    parsed = urlparse(url)
    netloc = parsed.netloc
    if "@" in netloc:
        host_part = netloc.rsplit("@", 1)[1]
        netloc = f"[REDACTED:userinfo]@{host_part}"

    # Keep the redaction marker literal in the rendered URL so callers can
    # eyeball it; only the original value gets percent-encoded if needed.
    safe = "[]:"
    query_pieces: list[str] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _URL_SECRET_QUERY_KEYS:
            redacted_value = _REDACTED_TEMPLATE.format(category="url_token")
        else:
            redacted_value = _redact_string(value)
        query_pieces.append(f"{quote(key, safe=safe)}={quote(redacted_value, safe=safe)}")
    new_query = "&".join(query_pieces)

    return urlunparse(parsed._replace(netloc=netloc, query=new_query))


def redact_in_place(target: MutableMapping[str, Any]) -> None:
    """Convenience for callers that hold a mutable dict (e.g. log extras)."""

    snapshot = redact(target)
    # The recursive function returns a new dict; copy back to preserve
    # caller's reference identity (logging adapters depend on this).
    target.clear()
    target.update(cast(dict[str, Any], snapshot))


__all__ = [
    "RedactionRule",
    "BUILTIN_RULES",
    "SECRET_KEY_NAMES",
    "add_allowlist_token",
    "clear_allowlist",
    "redact",
    "redact_headers",
    "redact_url",
    "redact_in_place",
]
