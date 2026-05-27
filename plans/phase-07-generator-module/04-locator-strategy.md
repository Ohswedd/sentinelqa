# Task 07.04 — Locator strategy & brittleness audit

## Objective

Enforce the locator-selection rules from CLAUDE §21/§22 across all generated code. Run the brittleness audit (Phase 04 task 04.06) and refuse to write any spec that fails it.

## Deliverables

- `engine/generator/locator_strategy.py` — Python-side wrapper that calls into the TS audit (via `sentinel-ts` subcommand `audit-locators`).
- A pre-write step in the generator that audits every rendered spec; if findings exist, fail the generation and report them.
- Configurable test-id attribute name (`tests.test_id_attribute`, default `data-testid`).
- A rule: brittle CSS like `:nth-of-type` allowed only when the page has no semantic alternative AND the renderer flags it with a `// sentinel: no-semantic-locator-available` comment.

## Steps

1. Wire the Python ↔ TS audit call.
2. Add a pre-write hook.
3. Add unit tests with brittle and non-brittle inputs.

## Acceptance criteria

- A deliberate brittle selector in a template fails the audit.
- Generation succeeds for the fixture app.

## Tests required

- `tests/unit/generator/test_locator_audit.py`.
- `tests/integration/generator/test_audit_blocks_brittle.py`.

## PRD / CLAUDE.md references

- PRD §9.3, §22.
- CLAUDE.md §21, §22.

## Definition of Done

- [ ] Audit wired and tested.
- [ ] Brittle output is blocked.
- [ ] `STATUS.md` updated.
