# Task 05.06 — OpenAPI / GraphQL ingestion

## Objective

Augment discovery with schemas when available. Improves planner quality and powers Phase 22 API testing.

## Deliverables

- `engine/discovery/openapi_ingest.py` — accepts a URL or a local file path; parses OpenAPI 3.0 / 3.1 (and Swagger 2.0 with a converter). Emits enriched `ApiEndpoint` records.
- `engine/discovery/graphql_ingest.py` — accepts a SDL file or a GraphQL endpoint (introspection query). Emits `ApiEndpoint` records for each operation.
- Config keys: `discovery.openapi.path` / `discovery.openapi.url`, same for `graphql`.
- When schemas are present, discovered endpoints get cross-validated:
  - Discovered endpoint not in schema → flagged (likely undocumented, possibly suspicious).
  - Schema endpoint not discovered → recorded as `expected_but_not_observed` (Planner can generate tests for them).

## Steps

1. Use `openapi-spec-validator` (Python) for OpenAPI; use a lightweight GraphQL parser (`graphql-core`).
2. Implement ingest functions returning typed structures.
3. Merge with crawler-detected endpoints.
4. Persist `api-schema.json` under the run dir.

## Acceptance criteria

- A fixture OpenAPI doc with 10 endpoints is ingested and merged.
- Introspection against a fixture GraphQL server (e.g. via `httpx`) produces typed records.
- Discovered-but-undocumented endpoints flagged.

## Tests required

- `tests/integration/discovery/test_openapi_ingest.py`.
- `tests/integration/discovery/test_graphql_ingest.py`.

## PRD / CLAUDE.md references

- PRD §9.1, §10.3.
- CLAUDE.md §9.

## Definition of Done

- [ ] OpenAPI + GraphQL ingest implemented.
- [ ] Cross-validation flags committed.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
