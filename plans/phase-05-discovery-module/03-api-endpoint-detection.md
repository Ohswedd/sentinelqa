# Task 05.03 — API endpoint detection

## Objective

Detect API endpoints called by the browser during crawling, classify them, and add them to the `DiscoveryGraph`.

## Deliverables

- `engine/discovery/api_detector.py` aggregating `network.request` / `network.response` events into `ApiEndpoint` records.
- Fields: method, path (template — `/api/users/[id]` from `/api/users/123`), auth strategy (heuristic: presence of Authorization header), response status distribution, average duration, response content-type, sample request/response (redacted).
- Path templating: simple param detection (numeric IDs, UUIDs, slugs) — produce a normalized template.
- Detect:
  - Endpoints called by browser flows that return 5xx during discovery (high-risk).
  - Endpoints referenced by the frontend (e.g. `/api/users` literal in JS) but **never called** during crawling — suspicious (flagged for Phase 19 LLM audit).
  - Mock-data smell: endpoints returning suspiciously static bodies (same response across calls).

## Steps

1. Build the aggregator.
2. Build the path-templating helper.
3. Use a lightweight JS scanner (regex over fetched JS bundles) to extract referenced endpoints; cross-check against discovered ones.
4. Persist `api.json` under the run dir.

## Acceptance criteria

- For a fixture app with 5 endpoints, all are detected with correct templates.
- 5xx endpoints flagged.
- Referenced-but-never-called endpoints flagged.

## Tests required

- `tests/integration/discovery/test_api_detector.py`.
- `tests/unit/discovery/test_path_templating.py`.

## PRD / CLAUDE.md references

- PRD §9.1, §10.3 API testing, §10.9 LLM audits.
- CLAUDE.md §9 Module contract.

## Definition of Done

- [ ] Endpoints aggregated and templated.
- [ ] Suspicious patterns flagged.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
