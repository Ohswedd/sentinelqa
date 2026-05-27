"""Property-based redaction tests (CLAUDE.md §33)."""

from __future__ import annotations

import json
import re

import pytest
from engine.policy.redaction import redact
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.slow


# A bounded JSON-like strategy. Plain strings are intentionally non-secret
# (lowercase short words) so the property "non-secrets survive" holds.
_safe_strings = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd", "Zs")),
    min_size=0,
    max_size=20,
)


def _json_strategy(depth: int = 3) -> st.SearchStrategy:
    leaves = st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        _safe_strings,
    )
    if depth <= 0:
        return leaves
    sub = _json_strategy(depth - 1)
    return st.one_of(
        leaves,
        st.lists(sub, max_size=5),
        st.dictionaries(_safe_strings.filter(lambda s: bool(s.strip())), sub, max_size=5),
    )


@given(_json_strategy())
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_redact_returns_json_serializable(value: object) -> None:
    out = redact(value)
    # Must serialize as JSON (the runtime contract for reports + audit log).
    json.dumps(out)


_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]{8,}", re.IGNORECASE),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
]


@given(st.sampled_from(["sk-abc1234567890abcdef1234", "AKIAIOSFODNN7EXAMPLE", "Bearer abcdefghi"]))
@settings(max_examples=50, deadline=None)
def test_known_secrets_never_survive(secret: str) -> None:
    out = redact(f"prefix {secret} suffix")
    assert secret not in out
    for pattern in _SECRET_PATTERNS:
        assert not pattern.search(str(out))
