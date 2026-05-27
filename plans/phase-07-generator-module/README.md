# Phase 07 — Generator Module

## Objective

Implement the **Generator** (PRD §9.3, §27): turn a `TestPlan` into idiomatic Playwright spec files, page objects, fixtures, and a generated plan markdown — all using **semantic locators** (CLAUDE §21, §22).

## PRD / CLAUDE.md references

- PRD §9.3 Generator, §22 Generated Test Rules (CLAUDE), §27 Example Generated Test.
- CLAUDE.md §21 TS rules, §22 Generated test rules.

## Sub-phases & tasks

1. `01-spec-templates.md` — Jinja2-style TS templates for each test type.
2. `02-page-objects.md` — Page-object generator using descriptor info from Phase 04.
3. `03-fixtures.md` — Auth fixture, data setup/teardown fixtures.
4. `04-locator-strategy.md` — Locator selection rules (semantic first); brittleness audit on output.
5. `05-generated-plan-md.md` — `sentinel.generated.plan.md` human-readable summary.
6. `06-generate-cli.md` — `sentinel generate` command.
7. `07-generator-tests.md` — Tests + golden generated specs for fixture app.

## Definition of Done

- Generated specs compile under `tsc` and run under Playwright.
- Locators are semantic; brittleness audit clean.
- Generated tests pass against the fixture app (E2E proof).
- Re-running generate is idempotent for the same plan.

## Phase Gate Review

- [ ] Generated specs compile and run.
- [ ] Brittleness audit clean.
- [ ] Idempotency verified.
- [ ] ADR-0012 (Generated test conventions) committed.
- [ ] `STATUS.md` updated.
