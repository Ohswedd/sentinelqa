"""Pluggable discovery backends ( 07, ADR-0010).

Importing this module triggers no Chromium / Playwright side effects;
adapters resolve lazily when constructed.
"""

from __future__ import annotations

from engine.discovery.backends.playwright_backend import (
    DEFAULT_TS_BINARY,
    PlaywrightCrawlBackend,
    PlaywrightCrawlInputs,
    PlaywrightDiscoveryError,
    PlaywrightRunner,
    SentinelTsNotInstalledError,
    SubprocessPlaywrightRunner,
    aggregate_result,
    extract_endpoints,
)

__all__ = [
    "DEFAULT_TS_BINARY",
    "PlaywrightCrawlBackend",
    "PlaywrightCrawlInputs",
    "PlaywrightDiscoveryError",
    "PlaywrightRunner",
    "SentinelTsNotInstalledError",
    "SubprocessPlaywrightRunner",
    "aggregate_result",
    "extract_endpoints",
]
