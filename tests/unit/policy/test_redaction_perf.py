"""Redaction performance test (marked `bench`, excluded from default run)."""

from __future__ import annotations

import json
import time

import pytest
from engine.policy.redaction import redact


@pytest.mark.bench
def test_redact_5mb_under_one_second() -> None:
    chunk = {
        "ok": "value",
        "password": "hunter2",
        "nested": {"token": "abc", "list": ["x"] * 50},
    }
    big = [chunk for _ in range(5000)]
    payload = json.loads(json.dumps(big))  # detach references
    start = time.perf_counter()
    redact(payload)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"Redaction took {elapsed:.3f}s; budget is 1.0s."
