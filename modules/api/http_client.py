"""Shared HTTP client + body-size guard for the API module.

Same shape as :mod:`modules.security.http_client`. The module never
ships an evasion path: User-Agent is fixed, no proxy rotation, no
fingerprint spoofing, and request bodies above
``negative_max_payload_kb`` (clamped at 64 KB by the config schema)
are refused at the client layer — not just at the check layer — so a
hypothetical bug in a check generator cannot produce a runaway
payload.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

import httpx

USER_AGENT: Final[str] = "SentinelQA-Api/1.0 (+https://sentinelqa.dev)"

# Absolute hard cap; the config schema already clamps `negative_max_payload_kb`
# at 64 KB, but the client refuses anything larger regardless of config to
# guarantee CLAUDE §30 ("no aggressive fuzzing") at the I/O layer.
ABSOLUTE_MAX_REQUEST_BYTES: Final[int] = 64 * 1024


class RequestTooLargeError(RuntimeError):
    """Raised when a check tries to send a body above the safe cap."""


@dataclass
class TokenBucket:
    """Per-second token bucket shared with :mod:`modules.security`."""

    rate_per_second: float
    capacity: float | None = None
    _tokens: float = field(default=0.0, init=False)
    _last_refill: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity or self.rate_per_second
        self._last_refill = time.monotonic()

    def take(self) -> None:
        cap = self.capacity or self.rate_per_second
        while True:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._last_refill = now
            self._tokens = min(cap, self._tokens + elapsed * self.rate_per_second)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            sleep_for = max(0.0, (1.0 - self._tokens) / self.rate_per_second)
            time.sleep(sleep_for)


def build_client(
    *,
    base_url: str,
    run_id: str,
    timeout_seconds: float,
    follow_redirects: bool = False,
) -> httpx.Client:
    headers = {
        "User-Agent": USER_AGENT,
        "X-SentinelQA-Test-Run": run_id,
        "Accept": "application/json, */*",
    }
    return httpx.Client(
        base_url=base_url,
        headers=headers,
        timeout=timeout_seconds,
        follow_redirects=follow_redirects,
    )


def safe_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    json_body: object | None = None,
    content: bytes | None = None,
    max_body_kb: int,
) -> httpx.Response:
    """Issue a request after rejecting oversized bodies.

    ``max_body_kb`` is the per-call cap derived from
    ``config.api.negative_max_payload_kb``. The absolute ceiling is
    :data:`ABSOLUTE_MAX_REQUEST_BYTES` regardless of caller intent.
    """

    cap = min(max_body_kb * 1024, ABSOLUTE_MAX_REQUEST_BYTES)
    payload_bytes = 0
    if content is not None:
        payload_bytes = len(content)
    elif json_body is not None:
        import json as _json  # local import — only when sending JSON

        # Estimate via a non-streaming serialisation; httpx would do the
        # same. We bound at `cap+1` to short-circuit huge payloads.
        encoded = _json.dumps(json_body).encode("utf-8")
        if len(encoded) > cap:
            raise RequestTooLargeError(
                f"refusing request body of {len(encoded)} bytes "
                f"(cap={cap}, absolute={ABSOLUTE_MAX_REQUEST_BYTES})"
            )
        content = encoded
        payload_bytes = len(encoded)
        json_body = None  # avoid double-serialisation by httpx
    if payload_bytes > cap:
        raise RequestTooLargeError(
            f"refusing request body of {payload_bytes} bytes "
            f"(cap={cap}, absolute={ABSOLUTE_MAX_REQUEST_BYTES})"
        )
    merged_headers = dict(headers or {})
    if content is not None and "Content-Type" not in merged_headers:
        merged_headers["Content-Type"] = "application/json"
    return client.request(
        method.upper(),
        url,
        headers=merged_headers,
        content=content,
    )


__all__ = [
    "ABSOLUTE_MAX_REQUEST_BYTES",
    "RequestTooLargeError",
    "TokenBucket",
    "USER_AGENT",
    "build_client",
    "safe_request",
]
