# Task 02.06 — Exit codes & JSON mode

## Objective

Lock in the deterministic exit-code mapping from PRD §13.2 and the CLAUDE §13 expanded set, and prove that `--json` mode emits **only** valid JSON to stdout.

## Prerequisites

- Tasks 02.01–02.05 complete.

## Deliverables

- `engine/policy/exit_codes.py` finalized with the union of PRD §13.2 and CLAUDE §13:
  - 0 success.
  - 1 quality gate failed.
  - 2 invalid config.
  - 3 runtime error (generic, when no more specific code fits).
  - 4 unsafe target blocked.
  - 5 dependency missing.
  - 6 test execution failed.
  - 7 internal error.
  - (Reserve 8+ for future use; document the reservation.)
- The mapping is reflected in `engine/errors/codes.py` (single source of truth).
- `apps/cli/sentinel/main.py` maps every `SentinelError` subclass to its code via `engine.policy.exit_codes.map_exception(exc)`.
- `apps/cli/sentinel/json_mode.py` — a context manager `json_stdout()` that:
  - Redirects all logging away from stdout.
  - Forces ANSI off.
  - Provides `emit(obj)` that writes one JSON object per line.
  - Asserts at process exit that stdout received nothing besides JSON (test-only check via env var).
- A CLI test for every exit code path.

## Steps

1. Reconcile the PRD §13.2 list with the CLAUDE §13 list. Where they overlap (e.g. PRD says "4 Test execution error", CLAUDE says "6 test execution failed"), follow CLAUDE §13 (CLAUDE §13 is the engineering constitution). Update `PRD.md` §13.2 to match in the same commit (CLAUDE §5).
2. Implement `map_exception()`.
3. Implement `json_stdout()`.
4. Write CLI tests that pipe stdout through a strict JSON parser; if any non-JSON byte appears, the test fails.

## Acceptance criteria

- Every defined exit code is reachable from a CLI invocation in tests.
- `sentinel audit --json --config bad.yaml` writes exactly one JSON object to stdout and exits 2.
- Logging in JSON mode goes to stderr only.

## Tests required

- `tests/integration/cli/test_exit_codes.py` — one test per code.
- `tests/integration/cli/test_json_mode_purity.py` — pipes stdout through `json.loads` line by line.

## PRD / CLAUDE.md references

- PRD §13.2 Exit codes.
- CLAUDE.md §13 CLI rules.

## Definition of Done

- [ ] Exit codes finalized; PRD §13.2 updated to match if it diverged.
- [ ] JSON-mode purity proven by tests.
- [ ] Every code reachable in tests.
- [ ] `STATUS.md` updated.
- [ ] If PRD changed, the PRD-sync row in `STATUS.md` filled.
