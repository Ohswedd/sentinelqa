"""Integration tests for the DOM map builder."""

from __future__ import annotations

from engine.discovery.crawler import Crawler, CrawlPolicy
from engine.discovery.dom_map import DomMapBuilder
from engine.domain.ids import IdGenerator
from pytest_httpserver import HTTPServer


def test_dom_map_extracts_form_inputs_and_buttons(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-DOMMAPAAAAAA",
        policy=CrawlPolicy(max_depth=1, max_pages=10, rate_limit_rps=50),
    )
    ids = IdGenerator()
    route_id_by_url = {p.url: ids.new("RT") for p in crawl.pages}
    dom = DomMapBuilder(id_generator=ids).build(crawl, route_id_by_url=route_id_by_url)

    # Expect at least one button (the "Click me" on the landing page) and
    # several inputs (email, freeform, orphan).
    roles = {el.role for el in dom.elements}
    assert "button" in roles
    assert "link" in roles
    # The email field has type=email mapping to textbox role.
    assert any(el.role == "textbox" for el in dom.elements)


def test_dom_map_observations_flag_missing_input_label(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-DOMOBSAAAAAA",
        policy=CrawlPolicy(max_depth=0, max_pages=1, rate_limit_rps=50),
    )
    ids = IdGenerator()
    route_id_by_url = {p.url: ids.new("RT") for p in crawl.pages}
    dom = DomMapBuilder(id_generator=ids).build(crawl, route_id_by_url=route_id_by_url)
    kinds = {o.kind for o in dom.observations}
    # The "freeform" input has no label and no aria-label.
    assert "input_missing_label" in kinds


def test_dom_map_marks_unreachable_links(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-DOMUNRAAAAAA",
        policy=CrawlPolicy(max_depth=2, max_pages=20, rate_limit_rps=50),
    )
    ids = IdGenerator()
    route_id_by_url = {p.url: ids.new("RT") for p in crawl.pages}
    dom = DomMapBuilder(id_generator=ids).build(crawl, route_id_by_url=route_id_by_url)
    assert any("/missing" in u for u in dom.unreachable_links)
