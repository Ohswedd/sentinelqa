# Task 02.08 — CLI test suite

## Objective

Lock in CLI behavior with a comprehensive integration suite using `typer.testing.CliRunner` and subprocess-level smoke tests.

## Prerequisites

- Tasks 02.01–02.07 complete.

## Deliverables

- `tests/integration/cli/` containing tests for:
  - Help, version, every command listed.
  - Global options propagation.
  - JSON mode purity.
  - Every exit code reachable.
  - `init` idempotency and `--force`.
  - `doctor` happy/unhappy paths.
  - Run lifecycle: happy, unsafe target, errored module, dry run.
  - Artifact tree creation.
  - `--ci` mode invariants.
- A subprocess smoke test that runs the installed `sentinel` binary in a tmpdir (verifies the console-script wiring).
- Coverage threshold: ≥ 90% across `apps/cli/`.

## Steps

1. Use `pytest` fixtures to manage tmp dirs and isolated `.sentinel/` trees.
2. Add `runner = CliRunner(mix_stderr=False)` so stdout/stderr can be asserted independently.
3. Capture and validate exit codes with `result.exit_code`.
4. For JSON-mode tests, assert each stdout line parses with `json.loads`.

## Acceptance criteria

- All listed test files exist and pass.
- Coverage threshold met.
- Subprocess smoke test runs `sentinel --version` and `sentinel doctor` successfully.

## Tests required

- (This task is the test suite.)

## PRD / CLAUDE.md references

- CLAUDE.md §16 Testing, §17 Quality gates.

## Definition of Done

- [ ] All CLI tests pass.
- [ ] Coverage ≥ 90% in `apps/cli/`.
- [ ] Subprocess smoke green.
- [ ] `STATUS.md` updated; Phase 02 ready for gate.
