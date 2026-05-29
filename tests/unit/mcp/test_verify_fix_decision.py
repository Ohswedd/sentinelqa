"""Unit tests for the verify-fix decision matrix."""

from __future__ import annotations

import pytest

from sentinelqa_mcp.verify_fix import _decide


@pytest.mark.parametrize(
    "prior,new,target,expected",
    [
        ({"a"}, set(), "a", "fix_verified"),
        ({"a"}, {"a"}, "a", "still_failing"),
        ({"a"}, {"a", "b"}, "a", "regressed"),
        ({"a", "b"}, {"b"}, "a", "partial"),
        ({"a"}, {"b"}, "a", "partial"),
        (set(), set(), None, "fix_verified"),
        (set(), {"x"}, None, "partial"),
        ({"a"}, {"a"}, None, "partial"),
    ],
)
def test_decide_matrix(prior: set[str], new: set[str], target: str | None, expected: str) -> None:
    decision, _ = _decide(
        target_finding_id="FND-TARGET" if target else None,
        target_fingerprint=target,
        prior_fingerprints=prior,
        new_fingerprints=new,
    )
    assert decision == expected
