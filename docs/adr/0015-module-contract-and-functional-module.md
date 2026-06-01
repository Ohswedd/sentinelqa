# ADR-0015: Module contract and functional module

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

ships the first concrete audit module (`functional`, the documentation) and, in doing so, has to commit to the contract every later module phase ( a11y, perf, security, LLM-code audit, visual, API, chaos) will reuse. Before, modules were a Phase-02 stub: the orchestrator's `run_modules` step called a `(config, decision)` factory and recorded a stringified return value; nothing typed, no findings translation, no per-module options channel.

Several pressures shaped the answer:

- **CLAUDE §9** mandates a seven-step lifecycle for every module: validate prerequisites → plan checks → execute → collect evidence → emit findings → emit metrics → summarize. Until nothing actually implemented those steps, so a future plugin author would have invented their own.
- **CLAUDE §10** requires module failures to produce typed partial results, not abort the run. rehomed the broad `except Exception` in `run_modules` so module crashes get categorized; has to wire the success path next to it.
- **our product spec** requires every medium/high/critical finding to carry evidence. The runner attaches evidence per `TestExecution`; the module has to translate those failures into `Finding` records with evidence intact.
- **CLAUDE §13** demands deterministic exit codes per command. `sentinel functional` has to map module + finding status onto the canonical 0/1/2/4/5/6 grid.
- ** / 07** already produce flow extractors and templated specs.'s tag conventions have to slot in without re-flowing the planner or generator.

We also wanted to ensure the contract is **observable from the lifecycle**. Before, `LifecycleContext.typed_module_results` existed but no module populated it; the CLI/SDK had no typed handle on module output.

## Decision

We adopt the following conventions for SentinelQA audit modules:

1. **The module contract lives in `engine/modules/base.py`.** `SentinelModule` is an `abc.ABC` with the seven CLAUDE §9 steps as instance methods. Subclasses must implement `execute(ctx, specs)`; the other six methods have working defaults so simple modules don't restate boilerplate. `run(ctx)` orchestrates the seven steps and is what the lifecycle calls. The companion `ModuleContext` dataclass freezes the inputs the orchestrator hands the module (config, safety decision, artifacts dir, run id, target, id generator, per-module options).

2. **Concrete modules live under `modules/<name>/`** so's plugin discovery can flip them on without restructuring. `modules/functional/__init__.py` re-exports `FunctionalModule` and self-registers with the process-wide `ModuleRegistry` on import. The factory `_factory(config, decision)` returns a fresh `FunctionalModule`; tests inject custom runners via the constructor's `runner_factory=` kwarg, never by replacing the global.

3. **The orchestrator detects `SentinelModule` instances and runs the full lifecycle.** `RunLifecycle.run_modules` calls `factory(config, decision)`; if the returned value is a `SentinelModule`, it builds a `ModuleContext`, calls `module.run(ctx)`, appends the typed `ModuleResult` to `ctx.typed_module_results`, and extends `ctx.typed_findings` with `module_result.findings`. The pre-Phase-10 "opaque value" path stays around for legacy registrations. `ModulePrerequisiteError` is a typed signal: the orchestrator records the module as `errored` with category `environment_failure` rather than crashing. `RunLifecycle.last_context` exposes the most-recent context so the CLI (and the future SDK in) can read typed results without a disk round-trip.

4. **Per-module options ride through the lifecycle.** `RunLifecycle.execute(... module_options={"functional": {...}})` threads each module's options into its `ModuleContext.options`. This is how `sentinel functional --mode smoke --grep @flow:login` reaches the FunctionalModule without coupling the orchestrator to module-specific knobs.

5. **Default findings translation is centralized.** `build_finding_from_failed_test` turns a failed/timed-out `TestExecution` into a typed `Finding` with our product spec evidence. When the runner didn't capture trace/screenshot/video (rare, but possible for synthesized failures), the helper falls back to the per-module runner log (`logs/runner.<module>.log`) so the medium-or-above evidence requirement is always met. Quarantined tests are skipped at the module layer, which is the same place the `quality_gate_passed` flag gets read by.

6. **Canonical Playwright tag set is generator-owned.** `engine.generator.pipeline._canonical_tag_set(flow)` always emits, in order: - `@p0..p3` (from `Flow.priority`). - `@module:<name>` (mapped from the planner extractor; defaults to `functional`). - `@flow:<extractor>` (the planner extractor name). - `@risk:<level>` (the canonical risk bucket). - Plus any planner-attached, ID-stripped tags (e.g. `@auth_boundary`). Slice modes translate to a Playwright `--grep` value: `smoke → @p0`, `standard → @p0|@p1`, `full → no filter`. `TagSelection.resolve(mode, user_grep)` is the single helper consumed by `sentinel functional` (and the upcoming CI modes). The TS runner forwards `--grep` to `playwright test` via a new `grep?: string` field on the run-config schema (Python + TS sides locked in parity).

7. **The `sentinel functional` CLI command drives the canonical lifecycle.** It loads config, applies CLI overrides (`--url`, `--retries`, `--workers`, `--shard`), resolves the tag selection, constructs `RunLifecycle`, and calls `execute(requested_modules=["functional"], module_options={"functional": {...}})`. Exit codes follow the standard grid: `0` (passed, no findings ≥ high), `1` (quality gate failed: module status `failed` or run `incomplete`), `2` (config / shard / mode error), `4` (unsafe target), `5` (runner binary missing), `6` (runner error). The command never reaches inside the lifecycle for state; it reads `lifecycle.last_context` for the typed module result.

## Consequences

- **Positive:** Future module phases (11, 12, 13, 19, 21, 22, 23) get a working seven-step ancestor + a typed registration path. The CLI gains a real `sentinel functional` command without growing a parallel runner driver. The reporter automatically sees typed findings from the lifecycle context — no new wiring. Tests can stub the runner per-instance, which is friendlier than monkey-patching globals.
- **Negative / trade-off:** `RunLifecycle` now has a small piece of mutable state (`_last_context`) that callers can read. We accept this because the alternative — returning a tuple from `execute` — breaks every existing call site, and the property is documented as "most recent execution only." The functional module's `validate_prerequisites` is a no-op; the `sentinel-ts` probe moved into `execute` (only fires when there are specs to run) so a project that hasn't generated yet doesn't see `errored` runs.
- **Follow-up obligations:** (a11y), (perf), (security), (LLM-code audit), (visual), (API), and (chaos) all subclass `SentinelModule` from this ADR. (quality scoring) reads `LifecycleContext.typed_findings` + `typed_module_results` to compute scores. (CI modes) consumes the `TagSelection` slice contract. (plugin architecture) replaces the import-time `register_with_default_registry` side effect with entry-point discovery, but the `SentinelModule` ABC + `ModuleContext` are the plugin contract.

## Alternatives considered

- **Push the seven-step lifecycle into the orchestrator.** Rejected: every module gets its own per-step idiosyncrasies (the security module's "validate prerequisites" is "check that the target is on the allowlist", not "check sentinel-ts is installed"), and forcing the orchestrator to dispatch into a fixed step table couples lifecycle to module semantics. Keeping the lifecycle inside the module (`module.run(ctx)`) lets each module enforce its own step ordering while the orchestrator stays stateless beyond context plumbing.
- **Pass module options via env vars or config-overlay files.** Rejected: env vars conflate CLI state with runtime state, and overlay files require tests to write throwaway YAML. A typed `module_options` mapping threaded through `LifecycleContext.options` is explicit and trivially mockable.
- **Make the generator emit `@module:<n>` only for non-functional modules.** Rejected: a consistent tag set is the only way slice modes (`@p0|@p1`) and module filters (`@module:api`) compose. Emitting the tag for every flow is one extra string per spec; the cost is rounding error.
- **Move the runner outcome → Finding translation into the runner.** Rejected: the runner is module-agnostic and emits `RunnerOutcome`. Findings are module-shaped (e.g. accessibility findings have different categories than security findings). Translation belongs in the module so each phase can override severity / category without touching the runner.

## References

- PRD section(s): our product spec, §10.1, §10.2, §18, §20, §21.3.
- our engineering rules rule(s): our engineering rules(Module contract), §10 (Run lifecycle), §13 (CLI), §16 (Testing standard), §17 (Quality gates), §24 (Findings), §37 (No placeholder completion).
- External: Playwright test tagging (`https://playwright.dev/docs/test-annotations#tag-tests`).
- Related ADRs: ADR-0007 (Run lifecycle), ADR-0008 (Report schemas), ADR-0009 (Python ↔ TS protocol), ADR-0012 (Generated test conventions), ADR-0013 (Runner architecture), ADR-0014 (Analyzer rules). will supersede the import-time registration mechanism with an entry-point ADR.
