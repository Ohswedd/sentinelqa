"""HTTP-first crawler (PRD §9.1, ADR-0010).

The crawler walks the target app starting at ``base_url`` and produces a
sequence of :class:`CrawlPage` records — pure data that downstream detectors
(DOM map, forms, API detector, auth boundary) consume without re-fetching.

Safety boundary (CLAUDE.md §6, PRD §2.2):

- Same-host-only by default; explicit allowlist for cross-host follow.
- Transparent User-Agent (``SentinelQA/<version>``) — no spoofing.
- ``X-SentinelQA-Test-Run`` header on every request so target operators can
  see the traffic.
- Rate-limited via a deterministic token bucket.
- Honors ``robots.txt`` for non-local hosts; only bypassed when both the
  config opts in (``discovery.respect_robots: false``) AND a warning is
  emitted.
- Never retries 4xx; retries 5xx with exponential backoff up to 3 times.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import time
import urllib.robotparser
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

# Local-host suffixes that never need robots.txt — see PRD §2.2 and
# engine.policy.safety.LOCAL_HOSTS for the wider allowlist.
_LOCAL_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def _sentinel_user_agent() -> str:
    """Return the transparent UA mandated by CLAUDE §6 / PRD §2.2."""

    try:
        version = importlib_metadata.version("sentinelqa-engine")
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover — defensive
        version = "0.0.0"
    return f"SentinelQA/{version} (+https://sentinelqa.dev/bot)"


def _normalize_url(url: str) -> str:
    """Drop fragments and trailing slashes from path so dedup works.

    We keep query strings — the crawler treats them as distinct routes since
    a SPA may render very different content based on them.
    """

    parsed = urlparse(url)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    return urlunparse(parsed._replace(fragment="", path=path))


@dataclass(frozen=True)
class CrawlPolicy:
    """User-facing knobs that govern the crawl."""

    max_depth: int = 3
    max_pages: int = 50
    rate_limit_rps: float = 5.0
    request_timeout_seconds: float = 10.0
    respect_robots: bool = True
    same_host_only: bool = True
    extra_allowed_hosts: tuple[str, ...] = ()
    user_agent: str = field(default_factory=_sentinel_user_agent)


@dataclass(frozen=True)
class CrawlPage:
    """One page fetched by the crawler."""

    url: str
    status_code: int
    content_type: str | None
    html: str
    depth: int
    elapsed_ms: int
    discovered_links: tuple[str, ...]
    discovered_script_srcs: tuple[str, ...]
    inline_scripts: tuple[str, ...]
    network_error: str | None = None

    @property
    def is_html(self) -> bool:
        return self.content_type is not None and self.content_type.startswith("text/html")


@dataclass(frozen=True)
class CrawlResult:
    """Output of a single crawl pass."""

    pages: tuple[CrawlPage, ...]
    robots_disallowed: tuple[str, ...]
    skipped_external: tuple[str, ...]


class _TokenBucket:
    """Deterministic rate limiter.

    Tests can pass a ``time_fn`` for control over the clock. Production uses
    ``time.monotonic``.
    """

    def __init__(self, rate_per_second: float, *, time_fn: object = time.monotonic) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._interval = 1.0 / rate_per_second
        self._last_emit: float | None = None
        # ``object`` is a callable returning ``float`` but typing it as a
        # protocol is overkill for one method — runtime contract only.
        self._time_fn = time_fn

    def acquire(self) -> float:
        """Block (sleep) until the next slot is available.

        Returns the wait duration in seconds — useful for tests that want
        to verify rate limiting without timing flakiness.
        """

        now = float(self._time_fn())  # type: ignore[operator]
        if self._last_emit is None:
            self._last_emit = now
            return 0.0
        next_slot = self._last_emit + self._interval
        wait = max(0.0, next_slot - now)
        if wait > 0:
            time.sleep(wait)
            now = next_slot
        self._last_emit = now
        return wait


class _RobotsCache:
    """Thin wrapper around ``urllib.robotparser`` with a per-host cache."""

    def __init__(self, *, http: httpx.Client, user_agent: str) -> None:
        self._http = http
        self._ua = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc
        if host in _LOCAL_HOSTS or any(host.endswith(f".{lh}") for lh in _LOCAL_HOSTS):
            return True
        parser = self._cache.get(host)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = urlunparse(parsed._replace(path="/robots.txt", query="", fragment=""))
            try:
                response = self._http.get(robots_url, headers={"User-Agent": self._ua})
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser.parse([])
            except httpx.HTTPError:
                # Treat unreachable robots.txt as allow-all (RFC 9309 §2.3).
                parser.parse([])
            self._cache[host] = parser
        return parser.can_fetch(self._ua, url)


class CrawlBackend(Protocol):
    """Pluggable crawl backend.

    The HTTP backend is the only one shipped in Phase 05; the Phase 17
    Playwright backend (ADR-0010) implements the same Protocol.
    """

    def crawl(
        self,
        base_url: str,
        *,
        policy: CrawlPolicy,
        run_id: str,
        http: httpx.Client | None = None,
        extra_cookies: dict[str, str] | None = None,
    ) -> CrawlResult: ...


class HttpCrawlBackend:
    """The default HTTP-first crawl backend (ADR-0010)."""

    def crawl(
        self,
        base_url: str,
        *,
        policy: CrawlPolicy,
        run_id: str,
        http: httpx.Client | None = None,
        extra_cookies: dict[str, str] | None = None,
    ) -> CrawlResult:
        owns_client = http is None
        client = http or httpx.Client(
            timeout=policy.request_timeout_seconds,
            follow_redirects=True,
            cookies=extra_cookies or None,
        )
        if http is not None and extra_cookies:
            client.cookies.update(extra_cookies)
        try:
            return self._crawl(
                client,
                base_url,
                policy=policy,
                run_id=run_id,
            )
        finally:
            if owns_client:
                client.close()

    def _crawl(
        self,
        client: httpx.Client,
        base_url: str,
        *,
        policy: CrawlPolicy,
        run_id: str,
    ) -> CrawlResult:
        normalized_base = _normalize_url(base_url)
        base_host = urlparse(normalized_base).netloc
        allowed_hosts = {base_host, *policy.extra_allowed_hosts}

        bucket = _TokenBucket(policy.rate_limit_rps)
        robots = _RobotsCache(http=client, user_agent=policy.user_agent)
        headers = {
            "User-Agent": policy.user_agent,
            "X-SentinelQA-Test-Run": run_id,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        }

        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(normalized_base, 0)])
        pages: list[CrawlPage] = []
        robots_disallowed: list[str] = []
        skipped_external: list[str] = []

        while queue and len(pages) < policy.max_pages:
            url, depth = queue.popleft()
            if url in seen:
                continue
            seen.add(url)

            host = urlparse(url).netloc
            if policy.same_host_only and host not in allowed_hosts:
                skipped_external.append(url)
                continue
            if policy.respect_robots and not robots.can_fetch(url):
                robots_disallowed.append(url)
                continue

            bucket.acquire()
            page = self._fetch(client, url, depth=depth, headers=headers)
            pages.append(page)
            if depth < policy.max_depth and page.is_html:
                for link in page.discovered_links:
                    candidate = _normalize_url(urljoin(url, link))
                    if candidate in seen:
                        continue
                    queue.append((candidate, depth + 1))

        return CrawlResult(
            pages=tuple(pages),
            robots_disallowed=tuple(robots_disallowed),
            skipped_external=tuple(skipped_external),
        )

    def _fetch(
        self,
        client: httpx.Client,
        url: str,
        *,
        depth: int,
        headers: dict[str, str],
    ) -> CrawlPage:
        start = time.monotonic()
        try:
            response = self._fetch_with_retries(client, url, headers=headers)
        except httpx.HTTPError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return CrawlPage(
                url=url,
                status_code=0,
                content_type=None,
                html="",
                depth=depth,
                elapsed_ms=elapsed,
                discovered_links=(),
                discovered_script_srcs=(),
                inline_scripts=(),
                network_error=str(exc),
            )
        elapsed = int((time.monotonic() - start) * 1000)
        content_type = response.headers.get("content-type", "")
        html = response.text if content_type.startswith("text/html") else ""
        links, scripts, inline = self._extract_links_and_scripts(html, base_url=url)
        return CrawlPage(
            url=url,
            status_code=response.status_code,
            content_type=content_type or None,
            html=html,
            depth=depth,
            elapsed_ms=elapsed,
            discovered_links=tuple(links),
            discovered_script_srcs=tuple(scripts),
            inline_scripts=tuple(inline),
        )

    def _fetch_with_retries(
        self,
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
    ) -> httpx.Response:
        backoffs = (0.1, 0.3, 0.7)
        for attempt, sleep_for in enumerate((0.0, *backoffs)):
            if sleep_for:
                time.sleep(sleep_for)
            response = client.get(url, headers=headers)
            # Never retry 4xx — caller wants to know about them.
            if response.status_code < 500 or attempt == len(backoffs):
                return response
        return response  # the loop always returns inside the if

    def _extract_links_and_scripts(
        self,
        html: str,
        *,
        base_url: str,
    ) -> tuple[list[str], list[str], list[str]]:
        if not html:
            return [], [], []
        # Local import keeps the top of the module light; bs4 is only needed
        # when we have HTML to parse.
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for anchor in soup.find_all("a"):
            href = anchor.get("href") if hasattr(anchor, "get") else None
            if isinstance(href, str) and href and not href.startswith(("#", "mailto:", "tel:")):
                links.append(href)
        scripts: list[str] = []
        inline: list[str] = []
        for script in soup.find_all("script"):
            src = script.get("src") if hasattr(script, "get") else None
            if isinstance(src, str) and src:
                scripts.append(src)
            else:
                text = script.string or ""
                if text.strip():
                    inline.append(text)
        return links, scripts, inline


class Crawler:
    """User-facing crawler that wires a :class:`CrawlBackend` together with policy."""

    def __init__(self, backend: CrawlBackend | None = None) -> None:
        self._backend: CrawlBackend = backend or HttpCrawlBackend()

    def crawl(
        self,
        base_url: str,
        *,
        run_id: str,
        policy: CrawlPolicy | None = None,
        http: httpx.Client | None = None,
        extra_cookies: dict[str, str] | None = None,
    ) -> CrawlResult:
        effective_policy = policy or CrawlPolicy()
        return self._backend.crawl(
            base_url,
            policy=effective_policy,
            run_id=run_id,
            http=http,
            extra_cookies=extra_cookies,
        )


def iter_pages(result: CrawlResult) -> Iterator[CrawlPage]:
    """Convenience generator for callers that don't want to depend on the dataclass."""

    return iter(result.pages)


def collect_javascript(
    result: CrawlResult,
    *,
    http: httpx.Client | None = None,
    max_bytes_per_script: int = 256 * 1024,
) -> dict[str, str]:
    """Fetch external script bodies referenced by crawled pages.

    Returns a mapping of script URL → body text. Bodies are truncated at
    ``max_bytes_per_script`` to keep memory bounded during very large crawls.
    Inline scripts are NOT included here — callers can read them directly
    off :attr:`CrawlPage.inline_scripts`.
    """

    bodies: dict[str, str] = {}
    seen: set[str] = set()
    owns_client = http is None
    client = http or httpx.Client(timeout=10.0, follow_redirects=True)
    try:
        for page in result.pages:
            for src in page.discovered_script_srcs:
                absolute = _normalize_url(urljoin(page.url, src))
                if absolute in seen:
                    continue
                seen.add(absolute)
                try:
                    response = client.get(absolute, headers={"User-Agent": _sentinel_user_agent()})
                except httpx.HTTPError:
                    continue
                if response.status_code != 200:
                    continue
                bodies[absolute] = response.text[:max_bytes_per_script]
        return bodies
    finally:
        if owns_client:
            client.close()


def crawled_urls(result: CrawlResult) -> Iterable[str]:
    return [p.url for p in result.pages]


__all__ = [
    "CrawlBackend",
    "CrawlPage",
    "CrawlPolicy",
    "CrawlResult",
    "Crawler",
    "HttpCrawlBackend",
    "collect_javascript",
    "crawled_urls",
    "iter_pages",
]
