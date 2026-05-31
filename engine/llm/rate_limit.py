"""Per-provider rate-limiter (Phase 30, ADR-0042).

A simple monotonic-clock token bucket. Each registered provider gets its
own bucket so a Gemini outage doesn't starve a separate Ollama call. The
bucket is in-memory only — there is no cross-process coordination, which
is intentional: SentinelQA runs are single-process by design (CLAUDE.md
§10), so a shared file-based bucket would only add fragility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from engine.errors.base import LlmRateLimitedError


@dataclass
class TokenBucket:
    """Standard token-bucket. Refills at ``rate_per_minute`` tokens / 60s."""

    capacity: int = 60
    rate_per_minute: float = 60.0
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        # Start full so the first call always succeeds. The downstream
        # CI runs are short-lived; a half-full bucket would just flake.
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def _refill(self, now: float) -> None:
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        added = (self.rate_per_minute / 60.0) * elapsed
        self._tokens = min(float(self.capacity), self._tokens + added)
        self._last_refill = now

    def try_consume(self, *, tokens: int = 1) -> bool:
        """Consume ``tokens`` from the bucket.

        Returns ``True`` on success, ``False`` if the bucket would go
        negative. Callers turn ``False`` into :class:`LlmRateLimitedError`.
        """

        now = time.monotonic()
        self._refill(now)
        if self._tokens < tokens:
            return False
        self._tokens -= tokens
        return True


@dataclass
class LlmRateLimit:
    """Public surface mounted on the registry.

    Holds one :class:`TokenBucket` per provider name. The default policy
    is 60 requests/min per provider; tests can override via the
    constructor or :meth:`set_policy`.
    """

    default_rate_per_minute: float = 60.0
    default_capacity: int = 60
    _buckets: dict[str, TokenBucket] = field(default_factory=dict)

    def bucket_for(self, provider: str) -> TokenBucket:
        bucket = self._buckets.get(provider)
        if bucket is None:
            bucket = TokenBucket(
                capacity=self.default_capacity,
                rate_per_minute=self.default_rate_per_minute,
            )
            self._buckets[provider] = bucket
        return bucket

    def set_policy(
        self,
        provider: str,
        *,
        rate_per_minute: float,
        capacity: int | None = None,
    ) -> None:
        bucket = TokenBucket(
            capacity=capacity if capacity is not None else int(rate_per_minute),
            rate_per_minute=rate_per_minute,
        )
        self._buckets[provider] = bucket

    def enforce(self, provider: str) -> None:
        """Consume one token; raise :class:`LlmRateLimitedError` on empty."""

        if not self.bucket_for(provider).try_consume(tokens=1):
            raise LlmRateLimitedError(provider=provider)


__all__ = ["LlmRateLimit", "TokenBucket"]
