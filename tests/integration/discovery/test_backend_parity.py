"""Backend parity test (task 17.07).

Drives the HTTP-first backend and the Playwright backend against the
same SSR fixture and asserts the produced :class:`CrawlResult` shapes
are equivalent under a canonical ordering. The HTTP backend talks to a
real httpx-served page via ``pytest_httpserver``; the Playwright
backend consumes a canned JSONL stream representing the same pages
(the real Chromium-driven path is exercised separately in
``test_playwright_backend_spa.py`` under the ``SENTINELQA_HAS_CHROMIUM``
gate).

A parity test that requires a real Chromium for both backends would be
flaky in default CI; this shape proves the translation contract while
still gating the Chromium-touching path on the env var.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("pytest_httpserver")
from engine.discovery.backends.playwright_backend import (  # noqa: E402
    PlaywrightCrawlBackend,
    PlaywrightCrawlInputs,
)
from engine.discovery.crawler import CrawlPolicy, HttpCrawlBackend  # noqa: E402
from pytest_httpserver import HTTPServer  # noqa: E402

HTML_INDEX = """<!doctype html>
<html><head><title>Index</title></head>
<body>
  <a href="/login">Login</a>
  <a href="/about">About</a>
</body></html>"""

HTML_LOGIN = """<!doctype html>
<html><head><title>Login</title></head>
<body><form><input name="email" /></form></body></html>"""

HTML_ABOUT = """<!doctype html>
<html><head><title>About</title></head>
<body>About us.</body></html>"""


class _StubPlaywrightRunner:
    """Returns a canned JSONL stream that mirrors what the real
    Chromium-driven backend would emit against the SSR fixture."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self.last_inputs: PlaywrightCrawlInputs | None = None

    def stream_jsonl(self, *, inputs: PlaywrightCrawlInputs) -> Iterator[str]:
        self.last_inputs = inputs
        envelope: dict[str, Any] = {
            "schema_version": "1.0.0",
            "ts": "2026-05-29T00:00:00.000Z",
        }
        # Identical URL set + depth ordering as the HTTP backend.
        yield json.dumps(
            {
                **envelope,
                "type": "discovery.page",
                "seq": 1,
                "url": f"{self._base_url}/",
                "status_code": 200,
                "content_type": "text/html",
                "depth": 0,
                "elapsed_ms": 5,
                "html": HTML_INDEX,
                "discovered_links": [
                    f"{self._base_url}/login",
                    f"{self._base_url}/about",
                ],
                "discovered_script_srcs": [],
            }
        )
        yield json.dumps(
            {
                **envelope,
                "type": "discovery.page",
                "seq": 2,
                "url": f"{self._base_url}/login",
                "status_code": 200,
                "content_type": "text/html",
                "depth": 1,
                "elapsed_ms": 5,
                "html": HTML_LOGIN,
                "discovered_links": [],
                "discovered_script_srcs": [],
            }
        )
        yield json.dumps(
            {
                **envelope,
                "type": "discovery.page",
                "seq": 3,
                "url": f"{self._base_url}/about",
                "status_code": 200,
                "content_type": "text/html",
                "depth": 1,
                "elapsed_ms": 5,
                "html": HTML_ABOUT,
                "discovered_links": [],
                "discovered_script_srcs": [],
            }
        )


def _serve_ssr_fixture(httpserver: HTTPServer) -> str:
    httpserver.expect_request("/").respond_with_data(HTML_INDEX, content_type="text/html")
    httpserver.expect_request("/login").respond_with_data(HTML_LOGIN, content_type="text/html")
    httpserver.expect_request("/about").respond_with_data(HTML_ABOUT, content_type="text/html")
    # robots.txt — empty (allow-all) so the HTTP backend doesn't refuse.
    httpserver.expect_request("/robots.txt").respond_with_data("", content_type="text/plain")
    return str(httpserver.url_for("/"))


def test_http_and_playwright_backends_produce_equivalent_routes(
    httpserver: HTTPServer,
) -> None:
    base_url = _serve_ssr_fixture(httpserver)
    policy = CrawlPolicy(
        max_depth=2,
        max_pages=5,
        rate_limit_rps=100.0,
        respect_robots=True,
        same_host_only=True,
    )

    http_backend = HttpCrawlBackend()
    http_result = http_backend.crawl(base_url, policy=policy, run_id="RUN-http")

    playwright_backend = PlaywrightCrawlBackend(runner=_StubPlaywrightRunner(base_url))
    pw_result = playwright_backend.crawl(base_url, policy=policy, run_id="RUN-pw")

    # The HTTP backend appends `/` to the index; the stub mirrors that.
    http_urls = sorted(p.url for p in http_result.pages)
    pw_urls = sorted(p.url for p in pw_result.pages)
    assert http_urls == pw_urls, f"backend parity violated: HTTP={http_urls!r} vs PW={pw_urls!r}"

    # Same depth distribution
    http_depths = sorted(p.depth for p in http_result.pages)
    pw_depths = sorted(p.depth for p in pw_result.pages)
    assert http_depths == pw_depths


def test_playwright_backend_threads_policy_into_inputs(
    httpserver: HTTPServer,
) -> None:
    base_url = _serve_ssr_fixture(httpserver)
    runner = _StubPlaywrightRunner(base_url)
    backend = PlaywrightCrawlBackend(runner=runner)
    backend.crawl(
        base_url,
        policy=CrawlPolicy(max_depth=4, max_pages=20, rate_limit_rps=3.0),
        run_id="RUN-pw",
    )
    assert runner.last_inputs is not None
    assert runner.last_inputs.max_depth == 4
    assert runner.last_inputs.max_pages == 20
    assert runner.last_inputs.rate_limit_rps == 3.0
