"""Gated CSR-SPA test for the Playwright discovery backend (task 17.07).

Runs only when ``SENTINELQA_HAS_CHROMIUM=1`` is set in the environment
(mirroring the Phase 04 chromium-smoke gating). Skipped by default in
local + CI runs that don't provision Chromium.

The test points the real :class:`SubprocessPlaywrightRunner` at the CSR
SPA fixture under ``packages/ts-runtime/fixtures/spa/`` and asserts the
backend produces at least one route — which the HTTP backend cannot do
because the landing page contains an empty `<div id="root"></div>`.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
from engine.discovery.backends.playwright_backend import PlaywrightCrawlBackend
from engine.discovery.crawler import CrawlPolicy

REPO_ROOT = Path(__file__).resolve().parents[3]
SPA_DIR = REPO_ROOT / "packages" / "ts-runtime" / "fixtures" / "spa"


pytestmark = pytest.mark.skipif(
    os.environ.get("SENTINELQA_HAS_CHROMIUM", "") != "1",
    reason="Set SENTINELQA_HAS_CHROMIUM=1 to run the CSR SPA gate.",
)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_playwright_backend_crawls_csr_spa(tmp_path: Path) -> None:
    if not SPA_DIR.is_dir():
        pytest.skip(f"SPA fixture missing at {SPA_DIR}")
    port = _pick_free_port()
    server = subprocess.Popen(
        ["node", "serve.mjs", str(port)],
        cwd=str(SPA_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Tiny wait for the server to come up.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)

        backend = PlaywrightCrawlBackend()
        result = backend.crawl(
            f"http://127.0.0.1:{port}/",
            policy=CrawlPolicy(max_depth=1, max_pages=3, rate_limit_rps=5.0),
            run_id="RUN-spa-gate",
        )
        assert len(result.pages) >= 1, "Playwright backend produced no pages"
    finally:
        server.terminate()
        try:
            server.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            server.kill()
