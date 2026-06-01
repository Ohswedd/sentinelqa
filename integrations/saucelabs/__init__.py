"""Sauce Labs remote-browser execution adapter."""

from __future__ import annotations

from integrations.saucelabs.runner import (
    SauceLabsQuotaExceeded,
    SauceLabsRunner,
    map_capabilities,
)

__all__ = [
    "SauceLabsRunner",
    "SauceLabsQuotaExceeded",
    "map_capabilities",
]
