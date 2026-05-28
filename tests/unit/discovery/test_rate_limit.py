"""Unit tests for the deterministic crawler token bucket."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from engine.discovery.crawler import _TokenBucket


class _FakeClock:
    def __init__(self, ticks: Iterator[float]) -> None:
        self._ticks = ticks

    def __call__(self) -> float:
        return next(self._ticks)


def test_first_acquire_returns_zero() -> None:
    bucket = _TokenBucket(rate_per_second=5.0, time_fn=_FakeClock(iter([0.0])))
    assert bucket.acquire() == 0.0


def test_zero_rate_rejected() -> None:
    with pytest.raises(ValueError):
        _TokenBucket(rate_per_second=0.0)


def test_immediately_subsequent_acquire_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("engine.discovery.crawler.time.sleep", lambda d: sleeps.append(d))
    # rate=5/s → interval=0.2s; calls at t=0 and t=0.05 → second waits 0.15s.
    clock = iter([0.0, 0.05])
    bucket = _TokenBucket(rate_per_second=5.0, time_fn=_FakeClock(clock))
    assert bucket.acquire() == 0.0
    wait = bucket.acquire()
    assert wait == pytest.approx(0.15, rel=1e-3)
    assert sleeps == [pytest.approx(0.15, rel=1e-3)]


def test_spaced_acquires_skip_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("engine.discovery.crawler.time.sleep", lambda d: sleeps.append(d))
    # rate=10/s → interval=0.1s. Calls at t=0, t=0.5 should not wait.
    bucket = _TokenBucket(rate_per_second=10.0, time_fn=_FakeClock(iter([0.0, 0.5])))
    bucket.acquire()
    wait = bucket.acquire()
    assert wait == 0.0
    assert sleeps == []
