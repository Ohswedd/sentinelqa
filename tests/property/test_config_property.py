"""Property-based config-edge-case tests."""

from __future__ import annotations

import pytest
from engine.config.schema import PolicyConfig
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

pytestmark = pytest.mark.slow


@given(st.integers(min_value=-10000, max_value=10000))
@settings(max_examples=100, deadline=None)
def test_policy_min_quality_score_bounds(score: int) -> None:
    if 0 <= score <= 100:
        cfg = PolicyConfig(min_quality_score=score)
        assert cfg.min_quality_score == score
    else:
        with pytest.raises(ValidationError):
            PolicyConfig(min_quality_score=score)
