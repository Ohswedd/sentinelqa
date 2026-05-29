"""Phase 00 smoke test.

Proves the test harness (pytest + pytest-asyncio + the strict pyproject config)
runs to completion before any product code exists. Extended in Phase 02 once
the real Typer app shipped (`sentinel_cli` exports the app) and in Phase 16
once the real SDK shipped (`sentinelqa` is now non-empty).
"""


def test_arithmetic_smoke() -> None:
    """Trivial assertion so pytest has at least one collected test."""
    assert 1 + 1 == 2


def test_packages_importable() -> None:
    """The CLI + Phase-16 SDK packages must import cleanly."""
    import sentinel_cli
    import sentinelqa

    # `sentinel_cli` exports the Typer app (Phase 02).
    assert "app" in sentinel_cli.__all__
    assert "build_app" in sentinel_cli.__all__
    # `sentinelqa` exports the Phase-16 SDK surface (ADR-0021).
    assert "Sentinel" in sentinelqa.__all__
    assert "AuditResult" in sentinelqa.__all__
