# Phase 05 — Discovery Module

## Objective

Implement the **Discovery** module (PRD §9.1): crawl the target app, build a route/element/form/API map, detect auth boundaries, ingest OpenAPI/GraphQL when available, and produce a `DiscoveryGraph` + `RiskMap` for the Planner to consume.

Discovery is read-only and safe by default; it must respect the safety policy at every request.

> **Scope note (ADR-0010):** Phase 05 ships an **HTTP-first** discovery MVP — `httpx` for fetching, `lxml`/`BeautifulSoup4` for HTML parsing, JS-bundle scanning for endpoint references. This covers SSR / hydrated / static apps. Pure CSR SPAs (Vite + React with empty `<div id="root">`) are out of scope for this phase; they are handled by `plans/phase-17-ci-integration/07-playwright-discovery-backend.md`, which adds a `PlaywrightCrawlBackend` behind the `CrawlBackend` Protocol defined here. The two backends must produce equivalent `DiscoveryGraph` shapes; downstream modules don't need to know which ran.

## PRD / CLAUDE.md references

- PRD §9.1 Discovery module, §11 Architecture.
- CLAUDE.md §6 Safety boundary, §9 Module contract, §10 Run lifecycle.
- ADR-0010 — Discovery MVP is HTTP-first; Playwright SPA crawl lands in Phase 17.

## Sub-phases & tasks

1. `01-crawler.md` — Polite link crawler with depth + rate limits.
2. `02-dom-interaction-map.md` — Elements, forms, buttons, ARIA, console errors.
3. `03-api-endpoint-detection.md` — Sniff XHR/fetch traffic; classify endpoints.
4. `04-forms-inventory.md` — Field-level inventory + submit-handler presence.
5. `05-auth-boundary-detection.md` — Login/logout/role transitions.
6. `06-openapi-graphql-ingest.md` — Optional schema imports.
7. `07-risk-map.md` — Derive risk scores per route/element.
8. `08-discovery-cli.md` — `sentinel discover` command + tests.

## Definition of Done

- `DiscoveryGraph` populated end-to-end for the Next.js example app (built in Phase 26 — for now, smoke against a tiny fixture).
- All HTTP requests respect rate limits and the safety policy.
- No fingerprint-evasion, no stealth flags.
- `RiskMap` produces stable, explainable scores.

## Phase Gate Review

- [ ] Discovery runs successfully against a local fixture.
- [ ] All requests logged in `audit.log` with redaction.
- [ ] OpenAPI ingestion verified with a sample spec.
- [ ] Risk map outputs documented and tested.
- [ ] `sentinel discover` exits 0 and writes `discovery.json` to the run dir.
- [ ] `STATUS.md` updated.
