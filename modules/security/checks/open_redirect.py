# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Open-redirect endpoint enumeration + bypass probe (v1.3.0).

The shipping ``ssrf_redirect`` check requires
``authorized_destructive`` mode and primarily targets SSRF. This
module covers the safer, defensive half: *enumerating* every URL
parameter that the application accepts a redirect target on, and
probing the standard bypass vectors against the application's
allowlist of trusted hosts.

The split is intentional:

* :func:`enumerate_redirect_params` — pure URL parsing. Given a list
  of discovered URLs / forms, return every (URL, param) pair where
  the param name matches the curated ``REDIRECT_PARAM_NAMES`` set.
* :func:`bypass_vectors` — pure payload generator. Given a trusted
  host (the app's allowlist), produce the canonical bypass payloads:
  protocol-relative, IPv4 / IPv6 encoded, ``@``-injection, double-URL
  encoding, dot-bypass, etc.
* :func:`evaluate_redirect_response` — pure inspector. Given an
  ``(input_payload, response_status, location_header)`` triple,
  return a structured :class:`RedirectFinding` if the response
  honours an off-allowlist redirect.

The HTTP probe itself lives in the security module's shell. This
module is intentionally I/O-free so the bypass matrix is testable
against synthetic fixtures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal
from urllib.parse import parse_qs, urlparse

# Parameter names that empirically accept a redirect target — drawn
# from a survey of OWASP, PortSwigger blog posts, and real CVEs.
REDIRECT_PARAM_NAMES: Final[frozenset[str]] = frozenset(
    {
        "url",
        "redirect",
        "redirect_uri",
        "redirect_url",
        "return",
        "return_to",
        "return_url",
        "returnto",
        "returnurl",
        "next",
        "rurl",
        "target",
        "dest",
        "destination",
        "checkout_url",
        "continue",
        "ref",
        "redir",
        "callback",
        "back",
        "back_url",
        "to",
        "u",
        "out",
        "go",
        "site",
    }
)


@dataclass(frozen=True, slots=True)
class RedirectCandidate:
    """A URL → query-parameter pair that should be probed."""

    url: str
    parameter: str


@dataclass(frozen=True, slots=True)
class RedirectFinding:
    """Structured finding for a successful open-redirect probe."""

    severity: Literal["critical", "high", "medium", "low", "info"]
    candidate: RedirectCandidate
    payload: str
    response_status: int
    location_header: str
    rationale: str


# --------------------------------------------------------------------------- #
# Enumeration
# --------------------------------------------------------------------------- #


def enumerate_redirect_params(urls: list[str]) -> tuple[RedirectCandidate, ...]:
    """Return every ``(url, parameter)`` pair worth probing.

    Each URL is parsed once; query-string keys are compared
    case-insensitively against :data:`REDIRECT_PARAM_NAMES`. The
    return order is deterministic (sort by URL, then param) so tests
    have a stable invariant.
    """

    seen: set[tuple[str, str]] = set()
    out: list[RedirectCandidate] = []
    for raw in urls:
        parsed = urlparse(raw)
        if not parsed.query:
            continue
        for key in parse_qs(parsed.query, keep_blank_values=True):
            lowered = key.lower()
            if lowered not in REDIRECT_PARAM_NAMES:
                continue
            keypair = (raw, key)
            if keypair in seen:
                continue
            seen.add(keypair)
            out.append(RedirectCandidate(url=raw, parameter=key))
    out.sort(key=lambda c: (c.url, c.parameter))
    return tuple(out)


# --------------------------------------------------------------------------- #
# Bypass payload generator
# --------------------------------------------------------------------------- #


def bypass_vectors(trusted_host: str) -> tuple[str, ...]:
    """Return the canonical bypass payloads against a trusted host.

    Each entry is a fully-qualified redirect URL designed to look
    plausibly like ``https://<trusted_host>/...`` to a naive
    allowlist (substring match, prefix match, suffix match) while
    actually pointing at ``attacker.test``.
    """

    attacker = "attacker.test"
    return (
        # Protocol-relative — older middleware misparses this.
        f"//{attacker}",
        # @-injection — RFC 3986 says everything before @ is userinfo.
        f"https://{trusted_host}@{attacker}",
        # Newline / CRLF injection — splits HTTP response headers.
        f"https://{trusted_host}%0a/{attacker}",
        # Path-as-host (some libraries treat second token as host).
        f"https:/{attacker}",
        f"https:/\\{attacker}",
        # Subdomain confusion.
        f"https://{trusted_host}.{attacker}",
        f"https://{attacker}.{trusted_host}",
        # Backslash bypass — interpreted differently across runtimes.
        f"https://{attacker}\\@{trusted_host}",
        # Mixed-case scheme — case-insensitive in URL spec.
        f"hTTpS://{attacker}",
        # IPv4 decimal encoding.
        "https://3232235521/",  # 192.168.0.1
        # IPv6 loopback bracket form.
        "https://[::1]/",
        # Double URL-encoded.
        f"https://%2F%2F{attacker}",
        # Dot bypass — trailing dot bypasses some host matchers.
        f"https://{trusted_host}./{attacker}",
    )


# --------------------------------------------------------------------------- #
# Response inspector
# --------------------------------------------------------------------------- #


_IS_REDIRECT_STATUS: Final[frozenset[int]] = frozenset({301, 302, 303, 307, 308})


def evaluate_redirect_response(
    *,
    candidate: RedirectCandidate,
    payload: str,
    response_status: int,
    location_header: str,
    trusted_hosts: frozenset[str],
) -> RedirectFinding | None:
    """Return a :class:`RedirectFinding` if the response is exploitable.

    Returns ``None`` when:

    * response is not a redirect (3xx with Location);
    * the redirect points back at an allowlisted host;
    * the redirect points at the empty string / a relative path.
    """

    if response_status not in _IS_REDIRECT_STATUS:
        return None
    if not location_header:
        return None

    target = _resolve_redirect_host(location_header)
    if target is None:
        return None  # relative path → safe

    if any(target == host or target.endswith(f".{host}") for host in trusted_hosts):
        return None  # stays in allowlist → safe

    # Distinguish "attacker honoured via payload" from "server picked
    # its own off-allowlist destination" — the former is a higher-fidelity
    # finding because it proves the parameter is the lever.
    payload_host = _resolve_redirect_host(payload)
    same_host = payload_host is not None and payload_host == target

    return RedirectFinding(
        severity="high" if same_host else "medium",
        candidate=candidate,
        payload=payload,
        response_status=response_status,
        location_header=location_header,
        rationale=(
            "Attacker-controlled payload was reflected in Location header"
            if same_host
            else "Redirect target is outside the configured trusted-host allowlist"
        ),
    )


# Internal helpers
_SCHEME_HOST_RE = re.compile(r"^\s*(?:[a-zA-Z][a-zA-Z0-9+.-]*:)?//([^/?#]+)")


def _resolve_redirect_host(location: str) -> str | None:
    """Pull the host out of a Location header value.

    Handles absolute (``https://example.com/path``), schemeless
    (``//example.com/path``), and unusual whitespace-prefixed values.
    Returns ``None`` for purely relative paths (``/login``).
    """

    if not location:
        return None
    match = _SCHEME_HOST_RE.match(location)
    if match is None:
        return None
    netloc = match.group(1)
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    return netloc.split(":")[0].lower().rstrip(".")


__all__ = [
    "REDIRECT_PARAM_NAMES",
    "RedirectCandidate",
    "RedirectFinding",
    "bypass_vectors",
    "enumerate_redirect_params",
    "evaluate_redirect_response",
]
