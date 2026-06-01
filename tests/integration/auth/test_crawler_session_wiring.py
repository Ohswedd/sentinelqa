"""vault → crawler injects cookies into the discovery client."""

from __future__ import annotations

import httpx
from engine.auth import Vault, cookies_for_host, load_storage_state_dict
from engine.discovery.crawler import (
    Crawler,
    CrawlPolicy,
    CrawlResult,
)

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


def test_crawler_receives_extra_cookies_from_vault(tmp_path) -> None:
    vault = Vault(root=tmp_path / "vault", key_store=StubKeyStore())
    vault.put(_make_entry(host="example.com", name="myorg"))

    storage = load_storage_state_dict(
        vault,
        host="example.com",
        name="myorg",
        allowed_hosts={"example.com"},
    )
    extra = cookies_for_host(storage, "example.com")
    # The test fixture stamps one cookie named ``session``.
    assert "session" in extra


def test_crawler_forwards_extra_cookies_to_backend(tmp_path) -> None:
    """Crawler.crawl(extra_cookies=…) reaches the backend.crawl call."""

    seen: dict[str, object] = {}

    class StubBackend:
        def crawl(
            self,
            base_url: str,
            *,
            policy: CrawlPolicy,
            run_id: str,
            http: httpx.Client | None = None,
            extra_cookies: dict[str, str] | None = None,
        ) -> CrawlResult:
            seen["extra_cookies"] = extra_cookies
            seen["base_url"] = base_url
            return CrawlResult(
                pages=(),
                robots_disallowed=(),
                skipped_external=(),
            )

    crawler = Crawler(backend=StubBackend())
    crawler.crawl(
        "https://example.com/",
        run_id="RUN-X",
        policy=CrawlPolicy(),
        extra_cookies={"session": "abc"},
    )
    assert seen["extra_cookies"] == {"session": "abc"}
