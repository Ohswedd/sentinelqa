# Task 06.01 — Deterministic planner core

## Objective

Implement the deterministic core: given a `DiscoveryGraph` + `RiskMap`, emit a `TestPlan` enumerating every flow and the test types it requires.

## Deliverables

- `engine/planner/core.py` with `class DeterministicPlanner`:
  - `plan(graph: DiscoveryGraph, risk: RiskMap, config: RootConfig) -> TestPlan`.
- Rules (deterministic, audited):
  - Every form → at least one functional test (P1 default; P0 if on a login/payment/admin route).
  - Every API endpoint → at least one API contract test (Phase 22 will execute it).
  - Every auth-required route → an auth-boundary functional test.
  - Every detected flow (login, signup, CRUD, admin) → priority based on risk (critical → P0, high → P1, medium → P2, low → P3).
  - For each route: a smoke test that asserts a successful page load + a stable anchor element.
  - For each form without a submit handler → flagged as an `LlmAuditCandidate` flow.
- Confidence per generated test case: deterministic rules → confidence 0.95; LLM rules → confidence per the adapter's response.
- Required auth role inferred from auth boundary detection.
- Required data state: tagged based on heuristics (`crud-create` needs no prior state; `crud-edit` needs an existing record fixture).

## Steps

1. Implement the planner with a small rules engine (data-driven; no spaghetti).
2. Emit `Flow` and `TestCase` records (typed Pydantic models from Phase 01).
3. Order flows by priority then risk.

## Acceptance criteria

- Same `DiscoveryGraph` always produces the same plan (deterministic).
- Plan covers every form, endpoint, auth boundary.

## Tests required

- `tests/unit/planner/test_deterministic_core.py` — rule coverage, ordering, determinism.
- `tests/golden/planner/test_fixture_plan.py` — locked plan for the fixture app.

## PRD / CLAUDE.md references

- PRD §9.2, §6.8.
- CLAUDE.md §9 Module contract, §22 Generated test rules.

## Definition of Done

- [ ] Deterministic plan implemented.
- [ ] Golden plan for fixture committed.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
