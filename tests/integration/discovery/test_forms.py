"""Integration tests for the forms inventory."""

from __future__ import annotations

from engine.discovery.crawler import Crawler, CrawlPolicy
from engine.discovery.forms import FormsInventory
from pytest_httpserver import HTTPServer


def test_forms_captured_with_fields(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-FORMSAAAAAAA",
        policy=CrawlPolicy(max_depth=0, max_pages=1, rate_limit_rps=50),
    )
    result = FormsInventory().build(crawl)
    # Landing page has 3 forms.
    assert len(result.forms) == 3
    # The contact form has a submit handler (action attr) AND validation
    # hints (required, type=email).
    contact = next(f for f in result.forms if str(f.action_url or "").endswith("/contact"))
    assert contact.submit_handler_present is True
    assert contact.validation_present is True
    # The "no-validation" form has a submit handler but no validation hints.
    no_val = next(f for f in result.forms if str(f.action_url or "").endswith("/no-validation"))
    assert no_val.submit_handler_present is True
    assert no_val.validation_present is False
    # The orphan form has neither submit handler nor validation.
    orphan_obs = {o.kind for o in result.observations}
    assert "form_missing_submit_handler" in orphan_obs


def test_forms_field_label_resolved(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-FORMSBBBBBBB",
        policy=CrawlPolicy(max_depth=0, max_pages=1, rate_limit_rps=50),
    )
    result = FormsInventory().build(crawl)
    contact = next(f for f in result.forms if str(f.action_url or "").endswith("/contact"))
    email = next(field for field in contact.fields if field.name == "email")
    assert email.accessible_label == "Email"
    assert email.type == "email"
    assert email.required is True
