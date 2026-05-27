# Task 09.01 — Failure categorization

## Objective

Classify each failed test into one of: `app_bug`, `test_bug`, `environment_failure`, `flake`, `data_setup_failure`, `auth_failure`, `api_failure`, `performance_regression`, `security_finding`, `accessibility_violation` (PRD §9.5).

## Deliverables

- `engine/analyzer/categorize.py` with rule-based classifier:
  - Network 4xx/5xx during test + assertion fails → `app_bug` (high confidence).
  - Locator timeout but app responded 200 → `test_bug` likely (medium confidence).
  - Browser crash, OOM, port conflict → `environment_failure`.
  - Same test passes on retry → `flake`.
  - Login step failed at fixture stage → `auth_failure`.
  - Axe violation → `accessibility_violation`.
  - Header check finding → `security_finding`.
  - Performance budget breached → `performance_regression`.
- Each category carries default confidence and evidence-pointing logic.

## Steps

1. Implement the rule pipeline.
2. Emit a `FailureClassification` record per failed test.
3. Add tests covering every category.
4. **Rehome the Phase-02 `run_modules` catch-all** (`engine/orchestrator/run_lifecycle.py::RunLifecycle.run_modules`): today it captures every `Exception` subclass into `ModuleOutcome(status="errored")` with no categorization. As part of Phase 09, the analyzer must categorize these into `environment_failure` / `app_bug` / `test_bug` and feed them through the same `FailureClassification` path. The data model already supports this via `engine.domain.module_result.ModuleResult` — extend `ModuleOutcome` (or replace it with `ModuleResult` directly) so the analyzer can read structured error context, not just a stringified type+message.

## Acceptance criteria

- Each fixture failure receives the expected category.
- Multiple categories possible (with confidence), but a single primary is picked.

## Tests required

- `tests/unit/analyzer/test_categorize.py` — every category.

## PRD / CLAUDE.md references

- PRD §9.5.
- CLAUDE.md §9, §24.

## Definition of Done

- [ ] Categorization rules covered.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
