"""Hypothesis property tests for the ID generator."""

from __future__ import annotations

import contextlib

import pytest
from engine.domain.ids import ENTITY_PREFIXES, ID_REGEX, IdGenerator, validate_id
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.slow


@given(st.sampled_from(sorted(ENTITY_PREFIXES)))
@settings(
    max_examples=200, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_generated_ids_match_regex(prefix: str) -> None:
    gen = IdGenerator()
    new = gen.new(prefix)
    assert ID_REGEX.match(new)
    assert validate_id(new, prefix=prefix) == new


@given(st.text())
def test_validate_id_robust_to_garbage(value: str) -> None:
    with contextlib.suppress(ValueError):
        validate_id(value)
