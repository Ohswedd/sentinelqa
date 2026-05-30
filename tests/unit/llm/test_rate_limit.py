"""Per-provider token-bucket rate-limiter."""

from __future__ import annotations

import time

import pytest
from engine.errors.base import LlmRateLimitedError
from engine.llm.rate_limit import LlmRateLimit, TokenBucket


def test_token_bucket_fills_then_drains() -> None:
    bucket = TokenBucket(capacity=2, rate_per_minute=60.0)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    # Third call denied — bucket empty.
    assert bucket.try_consume() is False


def test_token_bucket_refills_with_time(monkeypatch: pytest.MonkeyPatch) -> None:
    bucket = TokenBucket(capacity=1, rate_per_minute=60.0)  # 1 token / sec
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False

    # Advance the monotonic clock 1.5s so the bucket refills.
    real_monotonic = time.monotonic
    base = real_monotonic()

    def fake_monotonic() -> float:
        return base + 1.5

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    assert bucket.try_consume() is True


def test_rate_limit_enforce_raises_when_empty() -> None:
    limiter = LlmRateLimit(default_rate_per_minute=60.0, default_capacity=1)
    limiter.enforce("gemini")  # consumes the single token
    with pytest.raises(LlmRateLimitedError):
        limiter.enforce("gemini")


def test_rate_limit_per_provider_buckets_are_independent() -> None:
    limiter = LlmRateLimit(default_capacity=1, default_rate_per_minute=60.0)
    limiter.enforce("gemini")
    # OpenAI bucket still has its first token.
    limiter.enforce("openai")


def test_rate_limit_set_policy_overrides() -> None:
    limiter = LlmRateLimit(default_capacity=1, default_rate_per_minute=60.0)
    limiter.set_policy("groq", rate_per_minute=10.0, capacity=5)
    bucket = limiter.bucket_for("groq")
    assert bucket.capacity == 5
    assert bucket.rate_per_minute == 10.0
