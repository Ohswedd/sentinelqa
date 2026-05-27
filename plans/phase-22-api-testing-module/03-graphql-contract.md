# Task 22.03 — GraphQL contract validation

## Deliverables

- For each query/mutation in the SDL, send a sample operation and validate response shape.
- Detect:
  - Resolver returns `null` for non-nullable fields.
  - Missing fields.
  - Type mismatches.
- Subscription endpoints: probe with a short WebSocket connection.

## Acceptance criteria

- Fixture GraphQL server returning null on non-nullable field triggers finding.

## Tests required

- `tests/integration/modules/api/test_graphql_contract.py`.

## PRD / CLAUDE.md references

- PRD §10.3.
- CLAUDE.md §30.

## Definition of Done

- [ ] Validation + tests.
- [ ] `STATUS.md` updated.
