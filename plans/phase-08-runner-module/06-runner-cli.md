# Task 08.06 — `sentinel test` command

## Objective

Wire the runner into the CLI.

## Deliverables

- Replace Phase 02 stub of `test`.
- Options: `--path tests/sentinel`, `--grep`, `--workers`, `--shard`, `--browser`, `--docker`, `--retries`, `--config`, `--ci`, `--json`.
- Runs lifecycle steps relevant to execution (config, safety, runner). Skips discovery/planning/generation by default; `--with-generate` re-generates first.

## Steps

1. Implement the command, with `--docker` selecting the Docker runner.
2. Plumb every option.
3. Integration test against fixture.

## Acceptance criteria

- `sentinel test --docker` runs in CI and produces a `ModuleResult`.

## Tests required

- `tests/integration/cli/test_test_command.py`.

## PRD / CLAUDE.md references

- PRD §13.
- CLAUDE.md §13.

## Definition of Done

- [ ] CLI command implemented and tested.
- [ ] `STATUS.md` updated.
