# Task 06.02 — Flow extraction

## Objective

Identify named business flows (login, signup, logout, password reset, CRUD entities, search/filter/sort, role transitions, admin flows, payment sandbox, file upload/download, notification/email link flows) from the `DiscoveryGraph`.

## Deliverables

- `engine/planner/flows.py` — pluggable flow extractors. Each extractor inspects the graph and returns 0+ `Flow` records.
- Built-in extractors:
  - `LoginFlowExtractor` — finds login URL via config or heuristic (`/login`, `/sign-in`, form with email+password fields).
  - `SignupFlowExtractor`.
  - `LogoutFlowExtractor`.
  - `PasswordResetFlowExtractor`.
  - `CrudFlowExtractor` — detects CRUD patterns from REST URLs and forms.
  - `SearchFilterSortFlowExtractor`.
  - `AdminFlowExtractor`.
  - `RoleFlowExtractor` — detects role-based UI differences from anonymous vs authenticated passes.
  - `FileUploadDownloadFlowExtractor`.
  - `PaymentSandboxFlowExtractor` — looks for Stripe/PayPal/Square test integration markers; only sandbox flows; never production keys.
  - `NotificationFlowExtractor` — looks for email-link callback URLs (e.g. `/verify`, `/reset/[token]`).
- Each extractor publishes its `confidence`. Flows below 0.5 confidence are marked `confidence_low` and only proposed, not executed.

## Steps

1. Implement the extractor protocol and each built-in.
2. Order extractors deterministically.
3. Persist `flows.json` (subset of the plan).
4. Unit-test each extractor against tiny synthetic graphs.

## Acceptance criteria

- Fixture app's login + signup + at least one CRUD flow extracted.
- Each flow has steps, confidence, and priority.

## Tests required

- `tests/unit/planner/test_flow_extractors.py` per extractor.

## PRD / CLAUDE.md references

- PRD §9.2, §10.1 Functional flows.
- CLAUDE.md §9 Module contract.

## Definition of Done

- [ ] All listed extractors implemented and tested.
- [ ] Low-confidence flows handled distinctly.
- [ ] `STATUS.md` updated.
