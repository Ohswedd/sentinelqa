# Task 02.04 — Canonical run lifecycle orchestrator

## Objective

Implement the exact run lifecycle from CLAUDE §10 inside `engine/orchestrator/run_lifecycle.py`. Module phases (05+) plug into this orchestrator; it is the only path to executing a run.

## Prerequisites

- Tasks 02.01–02.03 complete.

## Deliverables

- `engine/orchestrator/run_lifecycle.py` exposing `class RunLifecycle` with a single public method:
  - `execute(config: RootConfig, *, requested_modules: list[str] | None, dry_run: bool, ci: bool) -> TestRun`
- The lifecycle implements every step from CLAUDE §10 in this order, with each step represented as a method:
  1. `load_config` (already loaded — verifies and freezes the snapshot).
  2. `validate_config` (re-runs `validate_config_dict`).
  3. `resolve_target` (URL parsing, host extraction).
  4. `enforce_safety_policy` (`SafetyPolicy.enforce`) — raises and exits early if rejected.
  5. `create_run_id` (UUIDv7 if available, else UUIDv4 with timestamp prefix).
  6. `create_artifact_directory` (uses task 02.05).
  7. `snapshot_config` (writes `config.snapshot.yaml`).
  8. `discover_app` — stub returning empty `DiscoveryGraph` until Phase 05.
  9. `build_execution_plan` — stub until Phase 06.
  10. `run_modules` — iterates registered modules; module phases register themselves.
  11. `collect_evidence` — aggregates evidence from module results.
  12. `normalize_findings` — applies redaction and schema versioning.
  13. `calculate_quality_score` — stub until Phase 14.
  14. `apply_quality_gates` — stub until Phase 14.
  15. `generate_reports` — stub until Phase 03/15.
  16. `persist_artifacts` — writes `run.json`, `findings.json`, etc.
  17. `return_deterministic_exit_code` — sets `TestRun.status`.
- A registration mechanism: `engine/orchestrator/registry.py` with `register_module(name, factory)` and `register_phase(step_name, hook)` so later phases can plug in real implementations.
- The orchestrator NEVER skips safety policy. It marks incomplete runs as `status="incomplete"` so reports stamp them honestly (CLAUDE §10).

## Steps

1. Define the module + step registry. Each module is registered at import time via an entry point or by an explicit `register_builtins()` call (start with explicit; entry points come in Phase 24).
2. Implement each lifecycle step with logging context (`LogContext(run_id=...)`).
3. Hooks return typed results; failures raise `TestExecutionError` but DO NOT abort the lifecycle — they're recorded as `ModuleResult(status="errored")` and the run continues unless the failure is in safety policy or config validation.
4. Implement `dry_run`: stop after `build_execution_plan` and emit the plan as the result.
5. Write a fluent integration test exercising the full lifecycle with stub modules.

## Acceptance criteria

- The lifecycle file is the **only** place the 17 steps are spelled out.
- An unauthorized target aborts at step 4 with exit code 4 and writes a minimal artifact directory containing `audit.log` and a stub `run.json` with `status="unsafe_blocked"`.
- A dry run produces a plan artifact and exits 0 without executing any module.
- A module raising an exception does not crash the run; the failure is captured in `ModuleResult.errors[]`.

## Tests required

- `tests/integration/orchestrator/test_lifecycle_happy.py` — stubs every module; full run produces artifacts.
- `tests/integration/orchestrator/test_lifecycle_unsafe_target.py` — exits 4, run marked unsafe_blocked.
- `tests/integration/orchestrator/test_lifecycle_module_error.py` — module raises; run continues.
- `tests/integration/orchestrator/test_lifecycle_dry_run.py`.

## PRD / CLAUDE.md references

- PRD §12 Workflows, §26 Skeleton.
- CLAUDE.md §10 Run Lifecycle, §11 Artifact rules.

## Definition of Done

- [ ] Every CLAUDE §10 step implemented and reachable.
- [ ] Registry allows later phases to plug in without modifying the lifecycle.
- [ ] Tests cover happy, unsafe, errored-module, and dry-run paths.
- [ ] ADR-0007 (Run lifecycle) committed.
- [ ] `STATUS.md` updated.
