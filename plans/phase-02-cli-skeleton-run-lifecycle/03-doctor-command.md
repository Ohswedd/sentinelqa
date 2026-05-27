# Task 02.03 — `sentinel doctor` command

## Objective

Implement a pre-flight check command that reports the health of the local environment, the config, and the target reachability. Exits 0 when healthy; non-zero with structured findings when not.

## Prerequisites

- Tasks 02.01–02.02 complete.

## Deliverables

`sentinel doctor` performs these checks (each emits a structured finding):

- Python version ≥ 3.11.
- Node version ≥ 20 (warn if missing; only required for the TS runtime phases).
- Playwright install present (`npx playwright --version`); browsers installed (`npx playwright install --dry-run`).
- `sentinel.config.yaml` exists and parses.
- Target `base_url` is allowlisted by the safety policy.
- Target `base_url` is reachable (`HEAD` request with 5 s timeout); non-200 is a warning, not a failure (the target may not be running yet).
- Required env vars from the config (`auth.username_env`, `auth.password_env`) are set when modules that need them are enabled.
- `.sentinel/` directory writable.
- Disk space ≥ 1 GB available for runs.

Output formats:

- Human: a table with ✓/⚠/✗ per check.
- JSON: `{ "status": "ok|warn|fail", "checks": [{name, status, detail, suggestion}] }` per CLAUDE §32.

Exit codes:

- 0 if no `fail`.
- 5 if any required dependency missing.
- 2 if config invalid.
- 4 if target unsafe.

## Steps

1. Implement each check as a small function returning a `DoctorCheck` record.
2. Aggregate results; format per mode.
3. Wire dependency checks via subprocess with timeouts.
4. Reachability check uses `httpx` with redirect-following and a tight timeout. Never sends auth.
5. Add `--fix` to `init` (NOT to doctor) when there are auto-fixable issues — for doctor itself, keep it read-only. (Auto-fixes belong to other commands, not doctor; CLAUDE §13.)

## Acceptance criteria

- On a clean machine with everything installed, `sentinel doctor` exits 0.
- Missing Playwright produces a precise suggestion (`npx playwright install --with-deps`).
- Missing env var produces an actionable message naming the variable.

## Tests required

- `tests/integration/cli/test_doctor_happy.py` — mocks subprocess to a healthy machine.
- `tests/integration/cli/test_doctor_failures.py` — each failure path mapped to its exit code.

## PRD / CLAUDE.md references

- PRD §12.1, §13.1.
- CLAUDE.md §13 CLI rules, §32 Error handling.

## Definition of Done

- [ ] Doctor implemented and tested.
- [ ] Human + JSON outputs identical in semantics.
- [ ] Exit codes deterministic.
- [ ] `STATUS.md` updated.
