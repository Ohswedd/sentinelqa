# Task 07.01 — Spec templates

## Objective

Author TypeScript Playwright spec templates for each common test type. Templates are rendered with deterministic substitution (Jinja2 or similar) to produce idiomatic, readable code.

## Deliverables

- `engine/generator/templates/` containing:
  - `smoke.spec.ts.j2` — loads route, asserts stable anchor.
  - `login.spec.ts.j2` — login flow (matches PRD §27 example).
  - `signup.spec.ts.j2`.
  - `logout.spec.ts.j2`.
  - `crud_create.spec.ts.j2`, `crud_read.spec.ts.j2`, `crud_update.spec.ts.j2`, `crud_delete.spec.ts.j2`.
  - `role_boundary.spec.ts.j2`.
  - `payment_sandbox.spec.ts.j2`.
  - `file_upload.spec.ts.j2`.
  - `api_contract.spec.ts.j2` (used by Phase 22).
  - `a11y_axe.spec.ts.j2`.
  - `perf_budget.spec.ts.j2`.
- Each template:
  - Uses `sentinelTest` from `@sentinelqa/playwright`.
  - Uses semantic locators only.
  - Includes explicit assertions; no `waitForTimeout`.
  - Includes negative cases where appropriate (PRD §27).
  - Tags tests (`@p0`, `@flow:login`, etc.) per the planner.
- `engine/generator/render.py` — typed renderer that takes a `Flow` + context and returns the rendered TS string. Renderer rejects any rendered output that fails the brittleness audit.

## Steps

1. Author each template; keep them small and composable.
2. Implement the renderer with strict variable validation (missing vars fail loudly).
3. Add a `tsc --noEmit` validation step over rendered output.

## Acceptance criteria

- Every template renders for the fixture app without errors.
- `tsc` accepts every rendered spec.
- Output matches PRD §27 example (or improves on it without breaking shape).

## Tests required

- `tests/golden/generator/test_templates_render.py` — locked outputs.
- `tests/integration/generator/test_tsc_accepts_output.py`.

## PRD / CLAUDE.md references

- PRD §9.3, §22 Generated Test Rules, §27 Example.
- CLAUDE.md §21, §22.

## Definition of Done

- [ ] All templates author + renderer pass tsc.
- [ ] Goldens locked.
- [ ] `STATUS.md` updated.
