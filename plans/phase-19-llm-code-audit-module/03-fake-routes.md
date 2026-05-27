# Task 19.03 — Fake routes and missing endpoints

## Deliverables

- Cross-reference internal links (anchors, `router.push` calls, `Link` components) with routes that the crawler actually reached.
- Cross-reference frontend-referenced API endpoints with detected endpoints.
- Findings:
  - `LLM-FAKE-ROUTE`: link points at `/foo` but `/foo` returns 404 → high.
  - `LLM-FAKE-ENDPOINT`: frontend code calls `/api/x` but no such endpoint observed and OpenAPI doesn't list it → medium-high.

## Acceptance criteria

- Fixture page linking to `/non-existent` triggers finding.
- Compliant page linking to `/dashboard` does not.

## Tests required

- `tests/integration/modules/llm_audit/test_fake_routes.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Cross-reference checks implemented.
- [ ] `STATUS.md` updated.
