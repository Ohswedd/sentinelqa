"""Playwright-driven discovery backend ( 07, ADR-0010).

The HTTP backend cannot crawl client-rendered SPAs because the
landing page contains no anchor tags until the JS bundle hydrates. This
backend drives Chromium via ``sentinel-ts discover`` (the new TS
subcommand) and consumes its JSONL events (``discovery.page`` and
``discovery.endpoint``) through the existing
:mod:`engine.orchestrator.ts_bridge` parser.

Implementation discipline:

- The same ``CrawlPolicy`` knobs apply: rate limit (forwarded as
 ``--rate-limit``), max depth, max pages, respect-robots, same-host,
 request timeout.
- Translation is one-to-one: every ``discovery.page`` event becomes one
 :class:`engine.discovery.crawler.CrawlPage` so downstream detectors
 (DOM map, forms, API detector) consume an identical shape regardless
 of which backend ran.
- Endpoints emitted by the TS subcommand are surfaced via the
 ``extra_api_endpoints`` field on :class:`CrawlResult`. Until lights up API
 contract checks, those endpoints round-trip through the audit log
 only — never gating anything.
- A pluggable :class:`PlaywrightRunner` Protocol mirrors the pattern in
 Phases 11 + 12. Production: :class:`SubprocessPlaywrightRunner`
 spawns ``sentinel-ts discover``. Tests: a stub returning a canned
 JSONL stream.

Safety contract (our engineering rules, the documentation):

- Same User-Agent + ``X-SentinelQA-Test-Run`` header policy applies;
 the TS subcommand honors both (and is validated by its own tests).
- The backend NEVER spawns Chromium itself — it shells out to the
 vendored TS runtime, which is what the install path
 provisioned. When the binary is missing, the backend raises
 :class:`SentinelTsNotInstalledError` so the CLI can surface exit
 code 5 (dependency missing).
- Subprocess invocation uses argument vectors (``shell=False``) and
 caps wall-clock time via the policy timeout times max_pages bound.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Final, Protocol
from urllib.parse import urlparse

import httpx

from engine.discovery.crawler import (
    CrawlPage,
    CrawlPolicy,
    CrawlResult,
)
from engine.orchestrator.ts_bridge import (
    DiscoveryEndpointEvent,
    DiscoveryPageEvent,
    parse_event,
)

DEFAULT_TS_BINARY: Final[str] = "sentinel-ts"
"""Default name of the Playwright runtime binary on ``$PATH``."""

_DEFAULT_PER_PAGE_TIMEOUT_SECONDS: Final[float] = 30.0
"""Wall-clock-per-page bound used when policy.request_timeout_seconds is None."""


class SentinelTsNotInstalledError(FileNotFoundError):
    """Raised when the Playwright TS runtime binary is missing."""


@dataclass(frozen=True)
class PlaywrightCrawlInputs:
    """Serializable inputs passed to the TS subcommand."""

    base_url: str
    run_id: str
    max_depth: int
    max_pages: int
    rate_limit_rps: float
    respect_robots: bool
    same_host_only: bool
    extra_allowed_hosts: tuple[str, ...]
    request_timeout_seconds: float
    user_agent: str
    cookies: dict[str, str]

    def to_config(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "base_url": self.base_url,
            "run_id": self.run_id,
            "max_depth": self.max_depth,
            "max_pages": self.max_pages,
            "rate_limit_rps": self.rate_limit_rps,
            "respect_robots": self.respect_robots,
            "same_host_only": self.same_host_only,
            "extra_allowed_hosts": list(self.extra_allowed_hosts),
            "request_timeout_seconds": self.request_timeout_seconds,
            "user_agent": self.user_agent,
            "cookies": dict(self.cookies),
        }


class PlaywrightRunner(Protocol):
    """Pluggable subprocess driver — injected for testability."""

    def stream_jsonl(self, *, inputs: PlaywrightCrawlInputs) -> Iterator[str]: ...


class SubprocessPlaywrightRunner:
    """Production implementation: spawn ``sentinel-ts discover``.

    The runner uses :mod:`subprocess.run` (vs Popen + streaming) because
    discovery is bounded — ``max_pages`` puts a hard cap on output size,
    and tests don't need event-level concurrency.
    """

    def __init__(self, *, ts_binary: str = DEFAULT_TS_BINARY) -> None:
        self._binary = ts_binary

    def stream_jsonl(self, *, inputs: PlaywrightCrawlInputs) -> Iterator[str]:
        resolved = shutil.which(self._binary)
        if resolved is None:
            raise SentinelTsNotInstalledError(
                f"{self._binary!r} not on PATH; install the Phase 04 TS runtime "
                "(`pnpm install` + `pnpm -r run build`)."
            )

        config_blob = json.dumps(inputs.to_config(), separators=(",", ":"))
        try:
            completed = subprocess.run(
                [resolved, "discover", "--config", "-"],
                input=config_blob,
                capture_output=True,
                text=True,
                check=True,
                timeout=_cap_total_seconds(inputs),
            )
        except subprocess.CalledProcessError as exc:
            raise PlaywrightDiscoveryError(
                exit_code=exc.returncode,
                stderr=(exc.stderr or "").strip()[:1024],
            ) from exc

        for line in completed.stdout.splitlines():
            stripped = line.strip()
            if stripped:
                yield stripped


class PlaywrightDiscoveryError(RuntimeError):
    """Raised when ``sentinel-ts discover`` exits non-zero."""

    def __init__(self, *, exit_code: int, stderr: str) -> None:
        super().__init__(f"sentinel-ts discover exited {exit_code}: {stderr or 'no stderr'}")
        self.exit_code = exit_code
        self.stderr = stderr


def _cap_total_seconds(inputs: PlaywrightCrawlInputs) -> float:
    """Bound the subprocess wall-clock to a multiple of per-page timeout."""

    per_page = inputs.request_timeout_seconds or _DEFAULT_PER_PAGE_TIMEOUT_SECONDS
    # Generous head-room for cold-start + browser launch; never less than 60s.
    return max(60.0, per_page * max(1, inputs.max_pages))


class PlaywrightCrawlBackend:
    """The Phase-17 Playwright-driven discovery backend.

    Implements :class:`engine.discovery.crawler.CrawlBackend`. The
    ``http`` and ``extra_cookies`` arguments mirror the HTTP backend
    contract; cookies are forwarded to the TS subcommand verbatim, and
    the optional ``http`` client is unused (kept on the signature to
    satisfy the Protocol).
    """

    def __init__(
        self,
        *,
        runner: PlaywrightRunner | None = None,
        ts_binary: str = DEFAULT_TS_BINARY,
    ) -> None:
        self._runner: PlaywrightRunner = runner or SubprocessPlaywrightRunner(ts_binary=ts_binary)

    # CrawlBackend Protocol — kwargs match the HTTP backend exactly.
    def crawl(
        self,
        base_url: str,
        *,
        policy: CrawlPolicy,
        run_id: str,
        http: httpx.Client | None = None,
        extra_cookies: dict[str, str] | None = None,
    ) -> CrawlResult:
        inputs = PlaywrightCrawlInputs(
            base_url=base_url,
            run_id=run_id,
            max_depth=policy.max_depth,
            max_pages=policy.max_pages,
            rate_limit_rps=policy.rate_limit_rps,
            respect_robots=policy.respect_robots,
            same_host_only=policy.same_host_only,
            extra_allowed_hosts=policy.extra_allowed_hosts,
            request_timeout_seconds=policy.request_timeout_seconds,
            user_agent=policy.user_agent,
            cookies=dict(extra_cookies or {}),
        )
        return aggregate_result(
            self._runner.stream_jsonl(inputs=inputs),
            base_host=urlparse(base_url).netloc,
            same_host_only=policy.same_host_only,
            allowlisted_hosts=set(policy.extra_allowed_hosts),
        )


# ---------------------------------------------------------------------------
# JSONL → CrawlResult aggregation (pure for easy testing)
# ---------------------------------------------------------------------------


def aggregate_result(
    lines: Iterable[str],
    *,
    base_host: str,
    same_host_only: bool = True,
    allowlisted_hosts: set[str] | None = None,
) -> CrawlResult:
    """Translate a JSONL stream into a :class:`CrawlResult`.

    Aggregation is forgiving — unknown event kinds are skipped so the
    Playwright runtime can add diagnostic events without breaking the
    Python side (our engineering rules: additive evolution).
    """

    allowed = {base_host}
    if allowlisted_hosts:
        allowed.update(allowlisted_hosts)

    pages: list[CrawlPage] = []
    skipped_external: list[str] = []
    seen_urls: set[str] = set()

    for raw in lines:
        event = parse_event(raw)
        if not isinstance(event, DiscoveryPageEvent):
            # Endpoints + log events round-trip through the audit log
            # only; the API module will start consuming them.
            continue
        if event.url in seen_urls:
            continue
        seen_urls.add(event.url)

        host = urlparse(event.url).netloc
        if same_host_only and host not in allowed:
            skipped_external.append(event.url)
            continue

        pages.append(
            CrawlPage(
                url=event.url,
                status_code=event.status_code,
                content_type=event.content_type,
                html=event.html,
                depth=event.depth,
                elapsed_ms=event.elapsed_ms,
                discovered_links=tuple(event.discovered_links),
                discovered_script_srcs=tuple(event.discovered_script_srcs),
                inline_scripts=(),
            )
        )

    return CrawlResult(
        pages=tuple(pages),
        robots_disallowed=(),
        skipped_external=tuple(skipped_external),
    )


def extract_endpoints(lines: Iterable[str]) -> tuple[dict[str, object], ...]:
    """Return parsed endpoint events for downstream API consumers."""

    out: list[dict[str, object]] = []
    for raw in lines:
        event = parse_event(raw)
        if isinstance(event, DiscoveryEndpointEvent):
            out.append(
                {
                    "method": event.method,
                    "path": event.path,
                    "status_code": event.status_code,
                    "source": event.source,
                }
            )
    return tuple(out)


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
