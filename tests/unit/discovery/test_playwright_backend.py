"""Unit tests for engine.discovery.backends.playwright_backend."""

from __future__ import annotations

import json

import pytest
from engine.discovery.backends.playwright_backend import (
    PlaywrightCrawlBackend,
    PlaywrightCrawlInputs,
    PlaywrightDiscoveryError,
    SentinelTsNotInstalledError,
    SubprocessPlaywrightRunner,
    aggregate_result,
    extract_endpoints,
)
from engine.discovery.crawler import CrawlPolicy

# ---------------------------------------------------------------------------
# Pure aggregation
# ---------------------------------------------------------------------------


def _page_event(
    *,
    seq: int,
    url: str,
    depth: int = 0,
    links: tuple[str, ...] = (),
) -> str:
    return json.dumps(
        {
            "type": "discovery.page",
            "schema_version": "1.0.0",
            "seq": seq,
            "ts": "2026-05-28T00:00:00.000Z",
            "url": url,
            "status_code": 200,
            "content_type": "text/html",
            "depth": depth,
            "elapsed_ms": 10,
            "html": "<html></html>",
            "discovered_links": list(links),
            "discovered_script_srcs": [],
        }
    )


def _endpoint_event(seq: int, *, method: str, path: str) -> str:
    return json.dumps(
        {
            "type": "discovery.endpoint",
            "schema_version": "1.0.0",
            "seq": seq,
            "ts": "2026-05-28T00:00:00.000Z",
            "method": method,
            "path": path,
            "status_code": 200,
            "source": "request",
        }
    )


def test_aggregate_produces_one_crawlpage_per_page_event() -> None:
    lines = [
        _page_event(seq=1, url="http://localhost:3000/"),
        _page_event(seq=2, url="http://localhost:3000/login", depth=1),
    ]
    result = aggregate_result(lines, base_host="localhost:3000")
    assert len(result.pages) == 2
    assert result.pages[0].url == "http://localhost:3000/"
    assert result.pages[1].depth == 1


def test_aggregate_skips_external_when_same_host_only() -> None:
    lines = [
        _page_event(seq=1, url="http://localhost:3000/"),
        _page_event(seq=2, url="http://evil.example/x"),
    ]
    result = aggregate_result(lines, base_host="localhost:3000", same_host_only=True)
    assert len(result.pages) == 1
    assert result.skipped_external == ("http://evil.example/x",)


def test_aggregate_dedupes_repeated_urls() -> None:
    lines = [
        _page_event(seq=1, url="http://localhost:3000/"),
        _page_event(seq=2, url="http://localhost:3000/"),
    ]
    result = aggregate_result(lines, base_host="localhost:3000")
    assert len(result.pages) == 1


def test_extract_endpoints_returns_dicts() -> None:
    lines = [
        _endpoint_event(seq=1, method="GET", path="/api/users"),
        _endpoint_event(seq=2, method="POST", path="/api/login"),
    ]
    endpoints = extract_endpoints(lines)
    assert endpoints == (
        {"method": "GET", "path": "/api/users", "status_code": 200, "source": "request"},
        {"method": "POST", "path": "/api/login", "status_code": 200, "source": "request"},
    )


def test_aggregate_skips_non_discovery_events() -> None:
    log_event = json.dumps(
        {
            "type": "log",
            "schema_version": "1.0.0",
            "seq": 1,
            "ts": "2026-05-28T00:00:00.000Z",
            "level": "info",
            "msg": "ok",
            "fields": {},
        }
    )
    result = aggregate_result(
        [
            log_event,
            _page_event(seq=2, url="http://localhost:3000/"),
        ],
        base_host="localhost:3000",
    )
    assert len(result.pages) == 1


def test_aggregate_passes_extra_allowlisted_hosts() -> None:
    lines = [
        _page_event(seq=1, url="http://api.example/x"),
    ]
    result = aggregate_result(
        lines,
        base_host="localhost:3000",
        same_host_only=True,
        allowlisted_hosts={"api.example"},
    )
    assert len(result.pages) == 1


# ---------------------------------------------------------------------------
# PlaywrightCrawlBackend with injected runner
# ---------------------------------------------------------------------------


class StubRunner:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.last_inputs: PlaywrightCrawlInputs | None = None

    def stream_jsonl(self, *, inputs):  # type: ignore[no-untyped-def]
        self.last_inputs = inputs
        yield from self._lines


def test_backend_translates_events_into_crawlresult() -> None:
    runner = StubRunner(
        [
            _page_event(seq=1, url="http://localhost:3000/"),
            _page_event(
                seq=2,
                url="http://localhost:3000/login",
                depth=1,
                links=("http://localhost:3000/",),
            ),
        ]
    )
    backend = PlaywrightCrawlBackend(runner=runner)
    result = backend.crawl(
        "http://localhost:3000/",
        policy=CrawlPolicy(max_pages=5, max_depth=2, rate_limit_rps=10.0),
        run_id="RUN-test",
    )
    assert len(result.pages) == 2
    # Inputs were translated correctly from policy.
    assert runner.last_inputs is not None
    assert runner.last_inputs.max_depth == 2
    assert runner.last_inputs.max_pages == 5
    assert runner.last_inputs.run_id == "RUN-test"


def test_backend_forwards_cookies() -> None:
    runner = StubRunner([])
    backend = PlaywrightCrawlBackend(runner=runner)
    backend.crawl(
        "http://localhost:3000/",
        policy=CrawlPolicy(),
        run_id="RUN-test",
        extra_cookies={"session": "abc"},
    )
    assert runner.last_inputs is not None
    assert runner.last_inputs.cookies == {"session": "abc"}


# ---------------------------------------------------------------------------
# Subprocess runner sanity (no real subprocess — just the not-installed path)
# ---------------------------------------------------------------------------


def test_subprocess_runner_raises_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "engine.discovery.backends.playwright_backend.shutil.which",
        lambda _bin: None,
    )
    runner = SubprocessPlaywrightRunner(ts_binary="sentinel-ts")
    inputs = PlaywrightCrawlInputs(
        base_url="http://localhost:3000/",
        run_id="RUN-test",
        max_depth=1,
        max_pages=1,
        rate_limit_rps=1.0,
        respect_robots=True,
        same_host_only=True,
        extra_allowed_hosts=(),
        request_timeout_seconds=5.0,
        user_agent="SentinelQA/test",
        cookies={},
    )
    with pytest.raises(SentinelTsNotInstalledError):
        list(runner.stream_jsonl(inputs=inputs))


def test_subprocess_runner_converts_subprocess_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "engine.discovery.backends.playwright_backend.shutil.which",
        lambda _bin: "/usr/local/bin/sentinel-ts",
    )

    class _Boom:
        returncode = 7
        stderr = "kaboom"

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        import subprocess

        raise subprocess.CalledProcessError(returncode=7, cmd=args[0], stderr="kaboom")

    monkeypatch.setattr(
        "engine.discovery.backends.playwright_backend.subprocess.run",
        fake_run,
    )

    runner = SubprocessPlaywrightRunner()
    inputs = PlaywrightCrawlInputs(
        base_url="http://localhost:3000/",
        run_id="RUN-test",
        max_depth=1,
        max_pages=1,
        rate_limit_rps=1.0,
        respect_robots=True,
        same_host_only=True,
        extra_allowed_hosts=(),
        request_timeout_seconds=5.0,
        user_agent="SentinelQA/test",
        cookies={},
    )
    with pytest.raises(PlaywrightDiscoveryError) as exc_info:
        list(runner.stream_jsonl(inputs=inputs))
    assert exc_info.value.exit_code == 7
    assert "kaboom" in str(exc_info.value)


def test_subprocess_runner_yields_lines_from_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "engine.discovery.backends.playwright_backend.shutil.which",
        lambda _bin: "/usr/local/bin/sentinel-ts",
    )

    class _Completed:
        stdout = '{"a":1}\n  \n{"b":2}\n'

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _Completed()

    monkeypatch.setattr(
        "engine.discovery.backends.playwright_backend.subprocess.run",
        fake_run,
    )
    runner = SubprocessPlaywrightRunner()
    inputs = PlaywrightCrawlInputs(
        base_url="http://localhost:3000/",
        run_id="RUN-test",
        max_depth=1,
        max_pages=1,
        rate_limit_rps=1.0,
        respect_robots=True,
        same_host_only=True,
        extra_allowed_hosts=(),
        request_timeout_seconds=5.0,
        user_agent="SentinelQA/test",
        cookies={},
    )
    out = list(runner.stream_jsonl(inputs=inputs))
    assert out == ['{"a":1}', '{"b":2}']


def test_inputs_to_config_round_trip() -> None:
    inputs = PlaywrightCrawlInputs(
        base_url="http://localhost:3000/",
        run_id="RUN-test",
        max_depth=2,
        max_pages=10,
        rate_limit_rps=4.0,
        respect_robots=False,
        same_host_only=True,
        extra_allowed_hosts=("api.example",),
        request_timeout_seconds=15.0,
        user_agent="SentinelQA/test",
        cookies={"k": "v"},
    )
    payload = inputs.to_config()
    assert payload["schema_version"] == "1"
    assert payload["base_url"] == "http://localhost:3000/"
    assert payload["extra_allowed_hosts"] == ["api.example"]
    assert payload["cookies"] == {"k": "v"}
