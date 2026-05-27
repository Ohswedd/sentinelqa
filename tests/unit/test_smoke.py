"""Phase 00 smoke test.

Proves the test harness (pytest + pytest-asyncio + the strict pyproject config)
runs to completion before any product code exists. Replace or extend in Phase 01
once real domain models land.
"""


def test_arithmetic_smoke() -> None:
    """Trivial assertion so pytest has at least one collected test."""
    assert 1 + 1 == 2


def test_placeholder_packages_importable() -> None:
    """The Phase-00 placeholder packages must import without side effects."""
    import sentinel
    import sentinel_cli

    assert sentinel.__all__ == []
    assert sentinel_cli.__all__ == []
