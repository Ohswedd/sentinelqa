"""Shared rate-limited HTTP client used by every security check.

Same building blocks as discovery: a token-bucket limiter,
transparent ``SentinelQA/<version>`` User-Agent, and the
``X-SentinelQA-Test-Run`` header so the operator of the target can
correlate hits in their access logs.

the engineering guidelines: there is no proxy rotation, no fingerprint
spoofing, no UA randomisation. Probes look like SentinelQA on the wire,
on purpose.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final

import httpx

USER_AGENT: Final[str] = "SentinelQA-Security/1.0 (+https://sentinelqa.dev)"


@dataclass
class TokenBucket:
    """Simple per-second token bucket (mirrors ``engine.discovery.crawler``)."""

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
    """Build a configured :class:`httpx.Client` for one security run.

    The base URL is informational only — callers always pass absolute or
    rooted URLs to :meth:`httpx.Client.request`. We set base_url so
    httpx exposes it on the request, which lets the redaction layer
    treat host paths consistently.
    """

    headers = {
        "User-Agent": USER_AGENT,
        "X-SentinelQA-Test-Run": run_id,
        "Accept": "*/*",
    }
    return httpx.Client(
        base_url=base_url,
        headers=headers,
        timeout=timeout_seconds,
        follow_redirects=follow_redirects,
    )


@dataclass(frozen=True)
class HttpProbeResult:
    """Snapshot of a probe response, with redacted-friendly accessors."""

    request_url: str
    status_code: int
    response_headers: tuple[tuple[str, str], ...]
    body_text: str
    elapsed_ms: int

    def headers(self) -> Iterator[tuple[str, str]]:
        return iter(self.response_headers)


__all__ = [
    "USER_AGENT",
    "TokenBucket",
    "build_client",
    "HttpProbeResult",
]
