# Task 06.05 — `sentinel plan` command

## Objective

Wire planner into the CLI: `sentinel plan --url …` (or `--from-discovery <path>`).

## Deliverables

- Replace Phase 02 stub of `plan`.
- Options: `--url`, `--from-discovery`, `--config`, `--llm/--no-llm`, `--output`, `--json`.
- Runs lifecycle steps 1–9 (config → plan); skips runner.
- Outputs `plan.json` and `plan.md`.

## Steps

1. Implement the command; reuse Phase 05 discovery output when `--from-discovery` provided.
2. Wire LLM flag through to the planner.
3. Integration test.

## Acceptance criteria

- `sentinel plan --url <fixture>` succeeds in CI without an LLM key.
- `--from-discovery .sentinel/runs/<id>/` reuses an existing graph.

## Tests required

- `tests/integration/cli/test_plan.py`.

## PRD / CLAUDE.md references

- PRD §13, §12.4.
- CLAUDE.md §13.

## Definition of Done

- [ ] CLI command implemented and tested.
- [ ] `STATUS.md` updated.
