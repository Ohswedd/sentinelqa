# Task 22.02 — OpenAPI contract validation

## Deliverables

- For each endpoint in the OpenAPI doc (Phase 05.06), send a representative request and validate response status, content-type, and schema.
- Use `openapi-core` or `jsonschema` for validation.
- Findings: schema mismatch, missing required response fields, wrong status code, unexpected content type.

## Acceptance criteria

- Fixture API with one endpoint returning `{}` instead of expected payload triggers a finding.

## Tests required

- `tests/integration/modules/api/test_openapi_contract.py`.

## PRD / CLAUDE.md references

- PRD §10.3.
- CLAUDE.md §30.

## Definition of Done

- [ ] Validation + tests.
- [ ] `STATUS.md` updated.
