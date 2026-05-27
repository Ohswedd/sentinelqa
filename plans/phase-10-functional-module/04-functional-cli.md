# Task 10.04 — `sentinel functional` command

## Objective

Wire the module into the CLI.

## Deliverables

- Replace Phase 02 stub of `functional`.
- Options: `--url`, `--config`, `--mode smoke|standard|full`, `--grep`, `--workers`, `--shard`, `--retries`, `--ci`, `--json`.
- Runs lifecycle, restricting modules to `functional`.
- Writes module result + findings to the run dir.

## Steps

1. Implement; reuse runner from Phase 08.
2. Tests.

## Acceptance criteria

- End-to-end `sentinel functional --url <fixture>` works.

## Tests required

- `tests/integration/cli/test_functional.py`.

## PRD / CLAUDE.md references

- PRD §13.
- CLAUDE.md §13.

## Definition of Done

- [ ] CLI command working.
- [ ] `STATUS.md` updated.
