"""Integration tests for the API endpoint detector."""

from __future__ import annotations

from engine.discovery.api_detector import ApiDetector
from engine.discovery.crawler import Crawler, CrawlPolicy, collect_javascript
from pytest_httpserver import HTTPServer


def test_api_detector_finds_observed_and_referenced(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    # Pre-seed the crawl with the API paths by visiting them directly.
    api_users = discovery_server.url_for("/api/users")
    api_items = discovery_server.url_for("/api/items/123")
    api_broken = discovery_server.url_for("/api/broken")

    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-APIDETAAAAAA",
        policy=CrawlPolicy(max_depth=1, max_pages=20, rate_limit_rps=50),
    )

    # Manually fetch the API endpoints so the detector sees them as observed.
    import httpx

    with httpx.Client() as client:
        from engine.discovery.crawler import CrawlPage, CrawlResult

        extra_pages = []
        for url in (api_users, api_items, api_broken):
            response = client.get(url)
            extra_pages.append(
                CrawlPage(
                    url=url,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    html="",
                    depth=1,
                    elapsed_ms=1,
                    discovered_links=(),
                    discovered_script_srcs=(),
                    inline_scripts=(),
                )
            )
        crawl = CrawlResult(
            pages=tuple([*crawl.pages, *extra_pages]),
            robots_disallowed=crawl.robots_disallowed,
            skipped_external=crawl.skipped_external,
        )

    js_bodies = collect_javascript(crawl)
    result = ApiDetector().detect(crawl, js_bodies=js_bodies)

    paths = {ep.path for ep in result.endpoints}
    # Observed endpoints map to their normalized paths.
    assert any(p.endswith("/api/users") for p in paths)
    assert any(p.endswith("/api/items/[id]") for p in paths)
    # 5xx is flagged.
    assert any(p.endswith("/api/broken") for p in result.observed_5xx_paths)
    # /api/hidden is referenced in bundle.js but never reached.
    assert any(p.endswith("/api/hidden") for p in result.referenced_only_paths)
    # Static-asset paths are never treated as API endpoints.
    assert not any(p.endswith("/static/main.css") for p in paths)
