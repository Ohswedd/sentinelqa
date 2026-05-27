# Task 05.01 — Polite crawler

## Objective

Crawl the target app starting at `base_url`, following only internal links, with strict rate-limiting and respect for `robots.txt` when the target is non-local.

## Deliverables

- `engine/discovery/crawler.py` exposing `Crawler` class with method `crawl(target, *, max_depth, max_pages, rate_limit_rps) -> CrawlResult`.
- Strict policies:
  - Only same-host links by default (configurable allowlist).
  - Honor `robots.txt` for non-local targets; bypass only with explicit config `discovery.respect_robots: false` AND a logged warning.
  - Rate limit (default 5 RPS, configurable).
  - User-Agent: `SentinelQA/<version> (+https://sentinelqa.dev/bot)` — transparent, no spoofing (CLAUDE §6).
  - Sends `X-SentinelQA-Test-Run: <run-id>` so app operators can see traffic (PRD §2.2).
  - No retries on 4xx; on 5xx retry with exponential backoff up to 3 times.
- Uses Playwright (via TS bridge) for crawling so client-rendered apps work, NOT just static HTML.
- Captures: discovered URLs, status codes, response sizes, console errors, network errors.
- `discovery.json` artifact under the run dir.

## Steps

1. Build the crawler using the Playwright runtime via Phase 04 bridge (emit `navigate` events, collect responses).
2. Implement BFS with `max_depth` and `max_pages`.
3. Implement robots.txt parsing (stdlib `urllib.robotparser`).
4. Add rate-limit token bucket.
5. Persist results.

## Acceptance criteria

- A local fixture crawl visits every reachable route under the limits.
- A test target that disallows in robots.txt is **not** crawled unless explicitly overridden.
- Rate limit enforced; verified by timing.

## Tests required

- `tests/integration/discovery/test_crawler_local_fixture.py` — uses a `pytest-httpserver` or static Vite fixture.
- `tests/unit/discovery/test_robots.py`.
- `tests/unit/discovery/test_rate_limit.py`.

## PRD / CLAUDE.md references

- PRD §9.1, §2.2 Compliant realism.
- CLAUDE.md §6, §26.

## Definition of Done

- [ ] Crawler implemented; honors robots, rate limits, allowlist.
- [ ] Transparent UA + test-run header sent.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
