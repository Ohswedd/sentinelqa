"""Phase 00 smoke test.

Proves the test harness (pytest + pytest-asyncio + the strict pyproject config)
runs to completion before any product code exists. Extended in Phase 02 once
the real Typer app shipped — `sentinel_cli` now exposes the app, so we just
check the import works rather than asserting `__all__` is empty.
"""


def test_arithmetic_smoke() -> None:
    """Trivial assertion so pytest has at least one collected test."""
    assert 1 + 1 == 2


def test_placeholder_packages_importable() -> None:
    """The placeholder + Phase-02 CLI packages must import cleanly."""
    import sentinel
    import sentinel_cli

    # python-sdk (`sentinel`) stays empty until Phase 16.
    assert sentinel.__all__ == []
    # `sentinel_cli` now exports the Typer app (Phase 02).
    assert "app" in sentinel_cli.__all__
    assert "build_app" in sentinel_cli.__all__
