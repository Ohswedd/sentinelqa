# ADR-0007: Run lifecycle

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

SentinelQA's value proposition (PRD §6, CLAUDE.md §45) is to answer a single question with evidence: _can this software be trusted enough to ship?_ That answer is only credible if every audit runs through the same, auditable lifecycle. CLAUDE.md §10 codifies the lifecycle as a 17-step sequence and §11 requires every run to leave a fully-isolated artifact tree behind. PRD §12 (Workflows) and §26 (Implementation Skeleton) reference the same structure.

Without a single canonical lifecycle, two failure modes become unavoidable:

1. Safety enforcement can drift to "best effort" — a module that forgets to call the policy enforcer can quietly bypass the safety boundary.
2. Reports diverge — a run that skipped a step but still wrote `run.json` looks identical to a complete run, which destroys the trust we are trying to build.

Phase 02 ships the CLI and needs the lifecycle to exist before later module phases (05+) can plug in. Module phases must extend the lifecycle without modifying it.

## Decision

The lifecycle is implemented exactly once in `engine/orchestrator/run_lifecycle.py` as `class RunLifecycle`. The class exposes a single public entry point — `execute(config, *, requested_modules, dry_run, ci) -> TestRun` — that walks the 17 CLAUDE §10 phases in order. Each phase is a method on the class so it is independently testable and so the canonical ordering is enforced by the class structure itself.

Module phases plug in via `engine/orchestrator/registry.py`:

- `ModuleRegistry.register_module(name, factory)` registers a callable invoked during step 10 (`run_modules`).
- `ModuleRegistry.register_phase_hook(phase, hook)` registers extra hooks for steps that intentionally aggregate from many sources (discovery, evidence, scoring, gates, reports).

The lifecycle never bypasses safety. Unsafe targets short-circuit at step 4 with the run marked `unsafe_blocked` and a minimal artifact tree (audit.log + run.json). Module failures during step 10 do NOT abort the lifecycle — they are captured as `ModuleOutcome(status="errored")` and the final status becomes `incomplete`, so reports stamp the run honestly (CLAUDE §10).

`--dry-run` is honored by stopping after step 9 (`build_execution_plan`) with `status="dry_run"`. CI mode (`--ci`) is recorded in the `LifecycleContext` so modules can branch on it without re-reading global state.

`run.json` is written during step 16. The final status is computed via a private `_finalize_status` helper invoked at the start of step 16 so the persisted artifact carries the same status the CLI returns from step 17. Step 17 then maps `status` to a CLI exit code via `engine.policy.exit_codes`.

## Consequences

- **Positive:** the lifecycle is auditable by reading one file. Adding a new step requires updating `LifecyclePhase` _and_ the class together, which is exactly the friction we want for a safety-critical sequence.
- **Positive:** modules and per-phase hooks are loosely coupled to the lifecycle, so Phase 24 (Plugin Architecture) can replace the registry with an entry-point loader without changing the lifecycle itself.
- **Positive:** safety policy is enforced exactly once, in step 4, and an unsafe target produces a deterministic exit code (4) and a non-empty audit log.
- **Negative / trade-off:** the class is moderately large (≈350 LOC). We accept that — splitting it across files would dilute the "one place" property the lifecycle relies on.
- **Follow-up obligations:**
  - Phase 03 will fill in the `generate_reports` hook with real report writers.
  - Phase 14 will fill in `calculate_quality_score` and `apply_quality_gates`.
  - Phase 24 will replace `register_builtins`-style registration with entry-point discovery, preserving the public registry interface.
  - Phase 29 will re-audit the lifecycle for determinism (no hidden network calls, deterministic ordering) as part of final hardening.

## Alternatives considered

- **Free-function lifecycle (no class).** Rejected: free functions sharing context via a `dict` make the call graph harder to follow and lose the natural seams for per-step unit tests. The class adds zero runtime cost and keeps each step independently testable.
- **Pipeline framework dependency (e.g. Luigi, Prefect).** Rejected: those frameworks ship orchestration, scheduling, persistence, and a UI we do not need. They would also leak framework concepts into the domain (PRD §11.2 forbids framework leakage into the core).
- **One module per step in its own file.** Rejected: the steps are short, share context, and only make sense in sequence. Splitting them would force a layer of glue we'd then have to debug separately.

## References

- PRD section(s): PRD §10 (Pillars), §12 (Workflows), §13 (CLI), §17 (Configuration), §26 (Implementation Skeleton).
- CLAUDE.md rule(s): CLAUDE.md §6 (Safety boundary), §9 (Module contract), §10 (Run Lifecycle), §11 (Artifact rules), §13 (CLI rules), §39 (CI rules).
- Related ADRs: ADR-0005 (Config schema), ADR-0006 (Safety policy).
