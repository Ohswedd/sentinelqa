"""Shared planner-test fixtures.

The deterministic planner relies on an :class:`IdGenerator` whose
``_random_slug`` produces stable slugs across runs. We patch it to a
counter so plan IDs become byte-stable, which is what the goldens depend
on.
"""

from __future__ import annotations

import pytest
from engine.domain.ids import IdGenerator


class _CountingIdGenerator(IdGenerator):
    def __init__(self) -> None:
        self._counter = 0

    def _random_slug(self) -> str:
        self._counter += 1
        # 12-char base-32 slug. Pad with 'A' from the alphabet (no I/L/O/U).
        body = f"{self._counter:08X}"
        return ("A" * (12 - len(body))) + body


@pytest.fixture
def deterministic_ids() -> IdGenerator:
    return _CountingIdGenerator()
