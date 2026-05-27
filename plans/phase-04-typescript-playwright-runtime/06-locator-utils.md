# Task 04.06 — Semantic locator utilities

## Objective

Provide reusable utilities for **semantic-first** locator selection. Used by the Generator (Phase 07) and the Healer (Phase 20).

## Deliverables

- `packages/ts-runtime/src/locators.ts` exposing:
  - `bestLocator(page: Page, target: ElementTarget): Promise<Locator>` — tries strategies in order: `getByRole`, `getByLabel`, `getByPlaceholder`, `getByText`, `getByTestId` (if a test-id attr is configured), `getByAltText`, `getByTitle`. Returns the first strategy with exactly one match.
  - `describeLocator(locator: Locator): Promise<LocatorDescriptor>` — captures role, accessible name, text, surrounding landmarks, so the Healer can regenerate when the DOM changes.
  - `auditLocatorBrittleness(spec: string): { warnings: string[] }` — static check of a generated spec; flags `.locator('div:nth-of-type(3)')` and other brittle patterns.
- Configurable test-id attribute (default: data-testid; configurable via `sentinel.config.yaml` → `tests.test_id_attribute`).
- Strict guard against brittle CSS unless no semantic option exists (CLAUDE §21).

## Steps

1. Implement the strategy chain.
2. Implement the descriptor (used by Phase 20 for healing).
3. Implement the static auditor (regex over a TS AST via `ts-morph`).
4. Unit tests against fixture DOMs.

## Acceptance criteria

- Given a button labeled "Sign in", `bestLocator` returns `getByRole('button', { name: /sign in/i })`.
- A spec with `page.locator('div:nth-of-type(3)')` triggers a brittleness warning.

## Tests required

- `tests/unit/locators.test.ts` — strategy chain + brittleness audit.

## PRD / CLAUDE.md references

- PRD §9.3 Generator, §27 Example test.
- CLAUDE.md §21 TS rules, §22 Generated test rules.

## Definition of Done

- [ ] Locator utilities exported.
- [ ] Brittleness audit catches obvious offenders.
- [ ] `STATUS.md` updated.
