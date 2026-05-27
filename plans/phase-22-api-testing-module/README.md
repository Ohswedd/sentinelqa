# Phase 22 — API Testing Module

## Objective

Implement API testing (PRD §10.3 / CLAUDE §30): contract validation against OpenAPI/GraphQL, negative cases, auth tests, latency budgets, response schema validation. Aggressive fuzzing forbidden against unauthorized targets (CLAUDE §30).

## PRD / CLAUDE.md references

- PRD §10.3 API testing.
- CLAUDE.md §9, §30 API testing rules.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `ApiModule`.
2. `02-openapi-contract.md` — Schema validation per endpoint.
3. `03-graphql-contract.md` — SDL/operation validation.
4. `04-negative-cases.md` — Missing required fields, wrong types, oversized payloads.
5. `05-auth-tests.md` — Unauthenticated/expired token/role-elevation tests.
6. `06-latency-budgets.md` — API p95 budget enforcement (overlaps Phase 12).
7. `07-pagination-and-error-shape.md` — Pagination boundaries + uniform error shape.
8. `08-backward-compat.md` — Compare today's schema with yesterday's (when history exists).
9. `09-api-cli.md` — `sentinel api` command.
10. `10-tests.md` — sweep.

## Definition of Done

- All checks implemented and tested against a fixture API.
- Aggressive fuzzing explicitly forbidden; safe payload-only flag enforced.
- ADR-0020 (API testing scope) committed.

## Phase Gate Review

- [ ] Contract validation works.
- [ ] Negative cases produce useful findings.
- [ ] Backward-compat detection works when history present.
- [ ] No unauthorized fuzzing path exists.
- [ ] `STATUS.md` updated.
