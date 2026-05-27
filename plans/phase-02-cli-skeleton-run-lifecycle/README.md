# Phase 02 — CLI Skeleton & Run Lifecycle

## Objective

Stand up the user-facing CLI (PRD §13) and the canonical run lifecycle (CLAUDE §10), with all artifact directories, exit codes, JSON mode, dry-run, and CI mode wired in. Module-specific subcommands are stubbed; their real implementations land in their own phases.

## PRD / CLAUDE.md references

- PRD §12 Workflows, §13 CLI, §17 Configuration, §26 Implementation Skeleton.
- CLAUDE.md §10 Run Lifecycle, §11 Artifact and Data Rules, §13 CLI rules, §43 Implementation Order (item 4).

## Sub-phases & tasks

1. `01-typer-app.md` — Typer app skeleton, global options, version, help.
2. `02-init-command.md` — `sentinel init` scaffolds `sentinel.config.yaml`, `tests/sentinel/`, `.sentinel/`, and CI templates.
3. `03-doctor-command.md` — `sentinel doctor` validates env, config, Playwright install, network reachability.
4. `04-run-lifecycle.md` — canonical run lifecycle orchestrator implementing CLAUDE §10 step by step.
5. `05-artifact-tree.md` — `.sentinel/runs/<run-id>/` layout, persistence helpers, retention policy.
6. `06-exit-codes-and-json-mode.md` — exit code mapping, JSON-only stdout in `--json` mode, ANSI suppression.
7. `07-dry-run-and-ci-mode.md` — `--dry-run` short-circuit and `--ci` defaults (no prompts, deterministic, fail-fast on unsafe).
8. `08-cli-tests.md` — pytest CLI smoke tests using `typer.testing.CliRunner`.

## Definition of Done

- `sentinel --help` enumerates every command from PRD §13.1 (most as stubs raising `NotImplementedError` until their phase).
- `sentinel init` produces a fully working skeleton in a temp directory.
- `sentinel doctor` returns 0 on a clean machine; non-zero with structured findings when a dependency is missing.
- A real run lifecycle stub (no real modules yet) creates `.sentinel/runs/<run-id>/` with `run.json`, `config.snapshot.yaml`, `audit.log`.
- `--json` mode emits only JSON; `--quiet` emits nothing on success.
- Every documented exit code is reachable and tested.

## Phase Gate Review

- [ ] `sentinel --help` lists every PRD §13.1 command.
- [ ] `sentinel init` smoke-tested.
- [ ] `sentinel doctor` smoke-tested.
- [ ] Lifecycle creates the correct artifact tree (CLAUDE §11).
- [ ] Exit codes 0–7 each covered by a CLI test.
- [ ] JSON mode: no log lines on stdout.
- [ ] ADR-0007 (Run lifecycle) committed.
- [ ] `STATUS.md` updated.
