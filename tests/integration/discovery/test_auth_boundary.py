"""Integration tests for auth boundary detection."""

from __future__ import annotations

from engine.discovery.auth_boundary import AuthBoundaryDetector, AuthCredentials
from engine.discovery.crawler import Crawler, CrawlPolicy
from engine.domain.ids import IdGenerator
from pytest_httpserver import HTTPServer


def test_anonymous_only_marks_dashboard_auth(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-AUTHANONAAAA",
        policy=CrawlPolicy(max_depth=1, max_pages=20, rate_limit_rps=50),
    )
    ids = IdGenerator()
    route_id_by_url = {p.url: ids.new("RT") for p in crawl.pages}

    detector = AuthBoundaryDetector(crawler=crawler)
    report = detector.detect(
        base_url=discovery_base_url,
        run_id="RUN-AUTHANONAAAA",
        policy=CrawlPolicy(max_depth=1, max_pages=20, rate_limit_rps=50),
        anonymous_crawl=crawl,
        credentials=None,
        route_id_by_url=route_id_by_url,
    )
    # /dashboard returned 401 anonymously → requires_auth=True.
    dashboard = next(v for v in report.verdicts if v.url.endswith("/dashboard"))
    assert dashboard.requires_auth is True
    assert any(b.route_id == route_id_by_url[dashboard.url] for b in report.boundaries)


def test_authenticated_pass_records_succeeded_login(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-AUTHLOGAAAAA",
        policy=CrawlPolicy(max_depth=1, max_pages=20, rate_limit_rps=50),
    )
    ids = IdGenerator()
    route_id_by_url = {p.url: ids.new("RT") for p in crawl.pages}

    login_url = discovery_server.url_for("/login")
    credentials = AuthCredentials(
        login_url=login_url,
        username_env_name="TEST_USER",
        password_env_name="TEST_PASS",
        username="admin",
        password="hunter2",
    )

    detector = AuthBoundaryDetector(crawler=crawler)
    report = detector.detect(
        base_url=discovery_base_url,
        run_id="RUN-AUTHLOGAAAAA",
        policy=CrawlPolicy(max_depth=1, max_pages=20, rate_limit_rps=50),
        anonymous_crawl=crawl,
        credentials=credentials,
        route_id_by_url=route_id_by_url,
    )
    assert report.login_succeeded is True
    assert report.username_env_name == "TEST_USER"
    # Authenticated pass sees /dashboard as 200; the verdict should record both statuses.
    dashboard = next(v for v in report.verdicts if v.url.endswith("/dashboard"))
    assert dashboard.anon_status == 401
    assert dashboard.auth_status == 200


def test_credentials_not_persisted_in_report(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    crawler = Crawler()
    crawl = crawler.crawl(
        discovery_base_url,
        run_id="RUN-AUTHSCRAAAAA",
        policy=CrawlPolicy(max_depth=0, max_pages=1, rate_limit_rps=50),
    )
    ids = IdGenerator()
    route_id_by_url = {p.url: ids.new("RT") for p in crawl.pages}

    credentials = AuthCredentials(
        login_url=discovery_server.url_for("/login"),
        username_env_name="TEST_USER",
        password_env_name="TEST_PASS",
        username="admin",
        password="super-secret-password",
    )

    detector = AuthBoundaryDetector(crawler=crawler)
    report = detector.detect(
        base_url=discovery_base_url,
        run_id="RUN-AUTHSCRAAAAA",
        policy=CrawlPolicy(max_depth=0, max_pages=1, rate_limit_rps=50),
        anonymous_crawl=crawl,
        credentials=credentials,
        route_id_by_url=route_id_by_url,
    )
    # The literal password must NOT appear anywhere in the report.
    serialized = repr(report)
    assert "super-secret-password" not in serialized
    assert report.username_env_name == "TEST_USER"
    assert report.password_env_name == "TEST_PASS"
