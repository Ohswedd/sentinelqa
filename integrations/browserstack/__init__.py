"""BrowserStack remote-browser execution adapter."""

from __future__ import annotations

from integrations.browserstack.runner import (
    BrowserStackQuotaExceeded,
    BrowserStackRunner,
    map_capabilities,
)

__all__ = [
    "BrowserStackRunner",
    "BrowserStackQuotaExceeded",
    "map_capabilities",
]
