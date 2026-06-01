# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""WebSocket + Server-Sent Events realtime auditing (v1.3.0).

The existing API checks cover HTTP. This module covers the two
realtime transports a modern app most often exposes:

* WebSockets — detected by ``ws://`` / ``wss://`` URLs in HTML +
  JS bundles, plus the ``Upgrade: websocket`` request header
  observed during discovery.
* Server-Sent Events — detected by ``Accept: text/event-stream``
  on requests + ``Content-Type: text/event-stream`` on responses.

Pure detectors. The production probe (a WebSocket handshake with
``Origin: https://attacker.test`` + a bounded message-size probe)
lives in the API module shell; this module classifies what discovery
already saw and produces structured findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class RealtimeEndpoint:
    """A realtime endpoint observed in the app."""

    kind: Literal["websocket", "sse"]
    url: str
    origin: str  # the page origin that opened it


@dataclass(frozen=True, slots=True)
class RealtimeFinding:
    code: str
    severity: Severity
    endpoint: RealtimeEndpoint
    rationale: str
    suggested_fix: str = ""


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

_WS_URL_RE = re.compile(r"\b(wss?://[A-Za-z0-9.\-:/_?=&%@~]+)", re.IGNORECASE)
_EVENT_SOURCE_RE = re.compile(r"new\s+EventSource\s*\(\s*['\"]([^'\"]+)['\"]")


def detect_websocket_endpoints(
    html: str,
    js_bundles: tuple[str, ...] = (),
    *,
    page_origin: str,
) -> tuple[RealtimeEndpoint, ...]:
    """Find every WebSocket URL referenced in HTML + JS bundles."""

    seen: set[str] = set()
    out: list[RealtimeEndpoint] = []
    for blob in (html, *js_bundles):
        for match in _WS_URL_RE.finditer(blob):
            url = match.group(1)
            if url in seen:
                continue
            seen.add(url)
            out.append(
                RealtimeEndpoint(
                    kind="websocket",
                    url=url,
                    origin=page_origin,
                )
            )
    return tuple(out)


def detect_sse_endpoints(
    html: str,
    js_bundles: tuple[str, ...] = (),
    *,
    page_origin: str,
) -> tuple[RealtimeEndpoint, ...]:
    """Find every ``new EventSource('...')`` call."""

    seen: set[str] = set()
    out: list[RealtimeEndpoint] = []
    for blob in (html, *js_bundles):
        for match in _EVENT_SOURCE_RE.finditer(blob):
            url = match.group(1)
            if url in seen:
                continue
            seen.add(url)
            out.append(
                RealtimeEndpoint(
                    kind="sse",
                    url=url,
                    origin=page_origin,
                )
            )
    return tuple(out)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def evaluate_websocket_handshake(
    endpoint: RealtimeEndpoint,
    *,
    accepted_origin: bool,
    enforces_origin: bool | None,
    allows_unbounded_messages: bool | None,
    requires_auth: bool | None,
) -> tuple[RealtimeFinding, ...]:
    """Classify a captured WebSocket handshake.

    ``accepted_origin`` records whether the server accepted a
    handshake from a cross-origin client. ``enforces_origin`` and
    ``allows_unbounded_messages`` may be ``None`` when the probe
    couldn't complete.
    """

    out: list[RealtimeFinding] = []
    if accepted_origin and enforces_origin is False:
        out.append(
            RealtimeFinding(
                code="WS-CROSS-ORIGIN-ACCEPTED",
                severity="high",
                endpoint=endpoint,
                rationale=(
                    "The server accepted a WebSocket handshake from an "
                    "off-origin client. Cross-Site WebSocket Hijacking "
                    "(CSWSH) is possible because session cookies travel "
                    "with the handshake by default."
                ),
                suggested_fix=(
                    "Validate the ``Origin`` header in the WebSocket "
                    "handler against the same allowlist that protects "
                    "the rest of the API."
                ),
            )
        )
    if allows_unbounded_messages is True:
        out.append(
            RealtimeFinding(
                code="WS-NO-MESSAGE-LIMIT",
                severity="medium",
                endpoint=endpoint,
                rationale=(
                    "Server accepted a 16 MiB inbound frame. Without an "
                    "upper bound an attacker can exhaust memory cheaply."
                ),
                suggested_fix="Configure a per-message and per-connection size cap.",
            )
        )
    if requires_auth is False:
        out.append(
            RealtimeFinding(
                code="WS-NO-AUTH",
                severity="high",
                endpoint=endpoint,
                rationale=(
                    "Handshake succeeded without any authentication "
                    "(cookie, token, or session header). Realtime data "
                    "should require the same auth as the REST surface."
                ),
                suggested_fix="Require an auth token / cookie on the upgrade.",
            )
        )
    return tuple(out)


def evaluate_sse_endpoint(
    endpoint: RealtimeEndpoint,
    *,
    auto_reconnect_seconds: float | None,
    sends_last_event_id: bool | None,
) -> tuple[RealtimeFinding, ...]:
    """Classify an SSE endpoint observed during discovery."""

    out: list[RealtimeFinding] = []
    if auto_reconnect_seconds is not None and auto_reconnect_seconds < 1.0:
        out.append(
            RealtimeFinding(
                code="SSE-RECONNECT-STORM",
                severity="medium",
                endpoint=endpoint,
                rationale=(
                    f"Client retry interval is {auto_reconnect_seconds:.2f}s. "
                    "A < 1s retry causes thundering-herd reconnects after a "
                    "transient outage."
                ),
                suggested_fix=(
                    "Send a ``retry: 3000`` field in the SSE stream so the " "browser backs off."
                ),
            )
        )
    if sends_last_event_id is False:
        out.append(
            RealtimeFinding(
                code="SSE-NO-LAST-EVENT-ID",
                severity="low",
                endpoint=endpoint,
                rationale=(
                    "Server ignores the ``Last-Event-ID`` header. Clients "
                    "miss events emitted during a reconnect."
                ),
                suggested_fix=("Honour ``Last-Event-ID`` and replay events with a " "higher id."),
            )
        )
    return tuple(out)


def _normalise_url(url: str) -> str:
    """Lower-case the scheme + host so dedupe is case-insensitive."""

    parsed = urlparse(url)
    if not parsed.netloc:
        return url
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"


__all__ = [
    "RealtimeEndpoint",
    "RealtimeFinding",
    "detect_sse_endpoints",
    "detect_websocket_endpoints",
    "evaluate_sse_endpoint",
    "evaluate_websocket_handshake",
]
