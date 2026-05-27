# Task 07.02 — Page objects

## Objective

Generate stable page-object classes for the most-used routes, encapsulating semantic locators and high-level actions. Page objects make repair safer (Phase 20).

## Deliverables

- `engine/generator/page_objects.py` producing one `<RouteName>Page.ts` per important route.
- Each page-object contains:
  - Imports from `@playwright/test`.
  - A `Page` reference.
  - Locator accessors (`get emailField()`, `get submitButton()`) using semantic strategies.
  - High-level action methods (`async login(email, password)`).
  - A `verify()` method asserting the page's identifying landmark.
- Naming: PascalCase + `Page` suffix; routes converted via `slugifyToCamel`.
- Page objects live under `tests/sentinel/pages/`.

## Steps

1. Pick which routes get a page object (rule: route appears in ≥ 2 flows OR has ≥ 3 interactive elements).
2. Generate methods from the DOM map.
3. Generate the `verify()` based on the route's identifying landmark from discovery.

## Acceptance criteria

- Generated page-objects compile.
- Used by generated specs (templates reference them).

## Tests required

- `tests/golden/generator/test_page_objects.py`.

## PRD / CLAUDE.md references

- PRD §9.3, §27.
- CLAUDE.md §21.

## Definition of Done

- [ ] Page objects generated for ≥ 2 routes in fixture.
- [ ] Compile + golden test.
- [ ] `STATUS.md` updated.
