# ADR-0010: Discovery release is HTTP-first; Playwright SPA crawl lands in

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

builds the Discovery module : the component that produces a
`DiscoveryGraph` (routes, elements, forms, API endpoints, auth boundaries) and
a `RiskMap` for the Planner to prioritize work against. Discovery
is the upstream input for every later module — Planner, Generator, Runner,
Functional, Security, LLM-Code Audit — so the shape it commits to here ripples
forward.

The task files written in aimed at a Playwright-driven
crawler invoked through the Python ↔ TS JSONL bridge. That target is
correct long-term: client-rendered apps (React/Vue/Svelte SPAs that hydrate
from an empty `<div id="root">`) need a real browser to render before
discovery can see any meaningful DOM. But the bridge is one-way
(Playwright → Python events); it has no RPC for Python to ask Playwright to
navigate-and-return-a-DOM-map synchronously. Building that RPC layer plus a
TS-side discovery driver plus matching Python plumbing in the same phase as
seven other modules is more scope than this phase can absorb without
sacrificing implementation depth or test coverage.

Constraints we must honor:

- our engineering rules(Safety boundary) — discovery must remain transparent, send the SentinelQA UA and run-id header, respect `robots.txt`, and apply rate limits.
- our engineering rules(Module contract) — discovery emits typed records, validates prerequisites, returns partial results on per-page failure rather than crashing the run.
- our engineering rules(Run lifecycle) — Steps 1–8 (load config → discover app) are what `sentinel discover` actually executes.
- the documentation — DiscoveryGraph + RiskMap are the contract+ depend on, regardless of how they were produced.

Empirical observation: most apps SentinelQA will audit (Next.js, Nuxt,
Remix, Astro, Django, Flask, Rails, FastAPI + Jinja) ship meaningful HTML on
the first response — server-rendered or hydrated-from-server. Pure CSR SPAs
(plain Vite + React with no SSR) are a real but smaller slice, and they are
also the slice most often produced by LLM coding agents (the documentation /
LLM-code audit). They deserve real treatment, but a Phase-17 CI lane is the
right home for that work because:

1. already provisions Chromium in CI (`npx playwright install`).
2. already wires the modes (fast/standard/full/nightly/release) that decide when a browser is worth spinning up.
3. The Python orchestrator pattern owns is the cleanest place to land a Playwright-driven discovery backend as a swap-in for the HTTP one.

## Decision

ships an **HTTP-first** Discovery release:

- The `Crawler` class in `engine/discovery/crawler.py` uses `httpx` (the package is already a workspace dev dep and ships in `apps/cli`) for all page fetching, with `lxml`/`BeautifulSoup4` for HTML parsing.
- It honors `robots.txt`, rate limits, the same-host allowlist, the transparent `SentinelQA/<version>` User-Agent, and the `X-SentinelQA-Test-Run: <run-id>` header (our engineering rules§2.2).
- DOM extraction (`engine/discovery/dom_map.py`), form inventory (`engine/discovery/forms.py`), and the JS-bundle endpoint scan in the API detector (`engine/discovery/api_detector.py`) all run against the HTML payload returned by the crawler — no browser execution.
- Auth boundary detection (`engine/discovery/auth_boundary.py`) runs two HTTP passes (anonymous + logged-in via `httpx.Client` with cookie jar); it never persists real credentials, only env-var names.
- The `Crawler` is declared via a `CrawlBackend` Protocol; the HTTP backend is the only one shipped in.

The `DiscoveryGraph` / `RiskMap` schemas are written so a Playwright-driven
backend can produce the same outputs in a future release without breaking
downstream consumers.

A Playwright-driven backend that handles CSR SPAs lands in as (added in
this PR). That task file commits to: a `sentinel-ts discover` subcommand in
`@sentinelqa/ts-runtime`, a `PlaywrightCrawlBackend` in Python that consumes
its JSONL events through the existing bridge, config wiring
(`discovery.engine: http | playwright`), and parity tests proving both
backends produce equivalent `DiscoveryGraph` shapes against a fixture SPA.

## Consequences

- **Positive:** ships a complete, testable, deterministic discovery pipeline. Every+ module gets a real `DiscoveryGraph` to consume. The HTTP backend is fast enough to run on every PR (no Chromium needed), which keeps the default CI lane cheap. The `CrawlBackend` Protocol is the contract plugs into — no rework of the consuming modules when the second backend arrives.
- **Negative / trade-off:** Pure CSR SPAs (Vite + React with no SSR) produce a near-empty `<body>` over HTTP, so the HTTP backend reports a small or empty `DiscoveryGraph` for them. Users hitting that case get a clear log warning and a `RiskMap` finding (`risk_model.rule = "spa_empty_body"`) telling them to switch to `discovery.engine: playwright` once ships it.
- **Follow-up obligations:** 1. must deliver task 07 (Playwright discovery backend) before the LLM-code audit phase can fairly run against CSR SPAs. **Resolved by task 07 (see ):** `engine/discovery/backends/playwright_backend.py` ships the `PlaywrightCrawlBackend`; the new `sentinel-ts discover` subcommand drives Chromium; `discovery.page` + `discovery.endpoint` event kinds are added to `ts-events.schema.json` and parsed by `engine.orchestrator.ts_bridge`; the CSR-SPA gate test runs under the new GitHub Actions lane `discovery-playwright (gated)` behind `SENTINELQA_HAS_CHROMIUM=1`. 2. the documentation is updated in this PR to reflect the HTTP-first release and the backend roadmap. 3. The `discovery.engine` config key is reserved in the loader so the backend can be enabled without a schema bump.

## Alternatives considered

- **Build the Playwright backend now alongside the HTTP one.** Rejected because it would require a new TS-side discovery driver, a bidirectional RPC over the JSONL bridge ( designed the bridge as one-way), and significant test coverage for both backends — too much scope to absorb alongside the other seven tasks without diluting either.
- **Ship a single Playwright-only backend and drop the HTTP path entirely.** Rejected because it makes the default CI lane depend on Chromium for every PR; raises the floor for contributors; and already gates Chromium behind `SENTINELQA_HAS_CHROMIUM=1`, signalling that browser- dependent paths should be opt-in until wires the CI mode.
- **Defer the whole `sentinel discover` CLI to.** Rejected because (Planner) and (Generator) consume `DiscoveryGraph`; if ships only the engine code without the CLI surface, the next two phases have no way to drive discovery end-to-end and would have to invent ad-hoc harnesses.

## References

- the documentation section(s): the documentation (Discovery module), §2.2 (Compliant realism), §11 (Architecture), §15 (TypeScript Runtime), §21 (CI/CD), §32 (Recommended Build Order).
- our engineering rules rule(s): §6 (Safety boundary), §8 (Runtime ownership), §9 (Module contract), §10 (Run lifecycle), §17 (Quality gates), §31 (LLM-Code audit), §34 (Documentation rules).
- Related ADRs: [ADR-0009](./0009-python-ts-protocol.md) (Python ↔ TS JSONL protocol — the bridge the backend will use).
