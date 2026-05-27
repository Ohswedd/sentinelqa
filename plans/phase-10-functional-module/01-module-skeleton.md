# Task 10.01 — Functional module skeleton

## Objective

Implement `modules/functional/` as the first concrete `SentinelModule` (CLAUDE §9). Sets the pattern other modules follow.

## Deliverables

- `modules/functional/__init__.py` exposing `FunctionalModule(SentinelModule)` with the standard lifecycle:
  - `validate_prerequisites(ctx)` — checks Playwright install, fixtures present.
  - `plan(ctx)` — filters the master plan to functional flows.
  - `execute(ctx)` — invokes runner with the functional spec set.
  - `collect_evidence(ctx, results)` — gathers artifacts.
  - `emit_findings(ctx, results)` — translates failures to `Finding`s.
  - `emit_metrics(ctx, results)` — pass/fail/duration counts.
  - `summarize(ctx)` — returns the module's `ModuleResult`.
- Registers itself with the orchestrator at import time via `register_module("functional", FunctionalModule)`.
- A module-failure produces a typed partial `ModuleResult` (CLAUDE §9) — never aborts the run.

## Steps

1. Implement the class against the abstract `SentinelModule` (PRD §26.3 / CLAUDE §9).
2. Register with the orchestrator.
3. Add a small unit test verifying the module's `summarize()` shape.

## Acceptance criteria

- Module shows up in `sentinel doctor` registry.
- Lifecycle steps callable.

## Tests required

- `tests/unit/modules/test_functional_skeleton.py`.

## PRD / CLAUDE.md references

- PRD §9, §10.1.
- CLAUDE.md §9, §10.

## Definition of Done

- [ ] Module class + registration.
- [ ] Skeleton tests.
- [ ] `STATUS.md` updated.
