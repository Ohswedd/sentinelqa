# Task 06.03 — `plan.json` schema

## Objective

Define and lock the canonical wire format for a test plan.

## Deliverables

- `packages/shared-schema/plan.schema.json`:
  - `schema_version`, `run_id`, `target`, `flows[]`, `test_cases[]`, `coverage_estimate` (per module).
  - `flows[]`: `id`, `name`, `description`, `priority`, `risk`, `confidence`, `steps[]`, `required_auth_role`, `required_data_state`, `tags[]`, `extractor`, `source` (`deterministic` | `llm`).
  - `test_cases[]`: `id`, `flow_id`, `test_type`, `file_path`, `confidence`, `module`.
- `engine/planner/plan_writer.py` writes `plan.json` and a human Markdown summary `plan.md`.
- Goldens for fixture-app plan.
- Round-trip test: plan → JSON → plan equals plan.

## Steps

1. Author schema; validate it.
2. Writer + Markdown.
3. Goldens + round-trip tests.

## Acceptance criteria

- Schema rejects plans without `schema_version`.
- Round-trip stable.

## Tests required

- `tests/golden/planner/test_plan_json.py`.
- `tests/unit/planner/test_plan_writer.py`.

## PRD / CLAUDE.md references

- PRD §9.2, §18.
- CLAUDE.md §11, §15.

## Definition of Done

- [ ] Schema + writer + goldens committed.
- [ ] `STATUS.md` updated.
