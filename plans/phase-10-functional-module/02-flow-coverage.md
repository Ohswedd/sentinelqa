# Task 10.02 — Flow coverage

## Objective

Ensure each flow type from PRD §10.1 is exercised when its conditions are met in the fixture/example app.

## Deliverables

- Flow types: login, signup, logout, password reset, CRUD (create/read/update/delete), search/filter/sort, multi-step forms, settings flows, role-based flows, admin flows, file upload/download, notification/email link flows, payment sandbox flows.
- For each: one or more rendered specs (from Phase 07), executed by the runner.
- Per-flow assertions:
  - **Login**: enters credentials, navigates to authenticated landmark, asserts session cookie set with `HttpOnly`+`Secure` if config requires.
  - **Signup**: creates user; cleans up via API or admin route in teardown.
  - **CRUD-create / -read / -update / -delete**: asserts persistence across navigation and refresh.
  - **Search/filter/sort**: asserts result set changes; pagination boundaries.
  - **Multi-step forms**: state preserved on back navigation; submit path verified.
  - **Role-based**: low-priv user cannot reach admin path; both UI hiding and backend 403 verified.
  - **Admin**: smoke tests on admin landing + at least one admin action.
  - **File upload/download**: small fixture file uploaded and downloaded; checksum verified.
  - **Notification/email link**: simulated by clicking a token URL pattern (no real email send unless configured).
  - **Payment sandbox**: uses Stripe/PayPal test keys via env; never real ones; production keys cause Hard Fail.

## Steps

1. Extend Phase 07 templates with the missing variants if needed.
2. Wire each into the Planner's deterministic core (Phase 06 already covers most; check coverage).
3. Add fixture pages in `packages/ts-runtime/fixtures/sample-app/` for each flow we want to demonstrate.

## Acceptance criteria

- Every flow type has at least one passing spec against the fixture.
- Payment-sandbox safety: real keys rejected.

## Tests required

- `tests/integration/modules/functional/test_flow_coverage.py`.

## PRD / CLAUDE.md references

- PRD §10.1.
- CLAUDE.md §9, §31.

## Definition of Done

- [ ] All §10.1 flow types covered.
- [ ] Payment sandbox safe.
- [ ] `STATUS.md` updated.
