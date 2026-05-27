# Task 02.07 — `--dry-run` and `--ci` modes

## Objective

Implement two cross-cutting modes that change behavior without changing commands. Both are referenced by PRD §13 and CLAUDE §39 (CI rules).

## Prerequisites

- Tasks 02.01–02.06 complete.

## Deliverables

- `--dry-run` on every command that performs side effects (`audit`, `discover`, `plan`, `generate`, `test`, `functional`, `api`, `a11y`, `perf`, `visual`, `security`, `chaos`, `llm-audit`, `fix`, `report`, `ci`). When set:
  - The orchestrator stops after `build_execution_plan` and writes only `run.json` (status `dry_run`), `plan.json`, and `config.snapshot.yaml`.
  - No network calls, no Playwright launches, no file mutations outside the run dir.
  - Exit 0 on success.
- `--ci` mode (default false; defaults to true when `SENTINEL_CI=true` env or CI=true env var detected). Effects:
  - No interactive prompts anywhere (CLAUDE §39).
  - Color disabled.
  - Fail-fast: the first unsafe-target check failure aborts the whole run.
  - Quality gates always evaluated; baselines never auto-accepted.
  - Artifacts always saved.
  - Exit code is the final answer; no log noise on stdout.
- A shared `RunMode` flag struct attached to `LogContext` so any module can branch on `ci=True`.

## Steps

1. Add `--dry-run` and `--ci` options to the Typer root or per-command.
2. Plumb them into `RunMode`.
3. Update the lifecycle to honor `dry_run`.
4. Update logging mode based on `ci` (forces `json` mode unless `--human` overrides).
5. Add tests for both modes covering each side-effect-producing command.

## Acceptance criteria

- `sentinel audit --dry-run` produces `plan.json` and exits 0 without launching Playwright.
- `CI=true sentinel audit --url http://localhost:3000` runs without prompts, in JSON mode, returns deterministic exit code.

## Tests required

- `tests/integration/cli/test_dry_run.py` — every effectful command.
- `tests/integration/cli/test_ci_mode.py` — verifies no prompts, JSON output, fail-fast on unsafe.

## PRD / CLAUDE.md references

- PRD §13 CLI, §21 CI/CD.
- CLAUDE.md §13 CLI rules, §39 CI rules.

## Definition of Done

- [ ] `--dry-run` honored everywhere.
- [ ] `--ci` mode deterministic, prompt-free, JSON.
- [ ] Tests cover both flags.
- [ ] `STATUS.md` updated.
