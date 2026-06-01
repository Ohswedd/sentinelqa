# ADR-0019: Quality scoring — reproducible 0..100 score + policy gate

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

our product spec (Quality Scoring Model) and our engineering rules(Quality score
rules) require SentinelQA to produce, at the end of every run, a
single 0..100 quality score plus a typed release decision (`pass`,
`pass_with_warnings`, `blocked`, `inconclusive`,
`unsafe_target_rejected`). The score must be:

- **Reproducible.** Same inputs → same `score.json` bytes; CI cannot flip on cosmetic re-runs.
- **Explainable.** A reviewer must be able to read off "why does this run score 87.25, why is it blocked, which finding triggered which rule?" without spelunking through code.
- **Composable.** Modules ship findings + module results into the lifecycle; the scoring layer is the only place that turns those into a numeric score and a release decision.
- **Reachable through the canonical exit-code grid** (the documentation) — `blocked` → exit 1, `unsafe_target_rejected` → exit 4, `inconclusive` → exit 6 (incomplete) or 0 (dry-run).

Phase 03 already shipped the wire format
(`packages/shared-schema/score.schema.json`) and the writer that
serializes a typed `QualityScore` + `PolicyDecision`. Phase 14 is the
first phase that _computes_ those objects rather than hand-stuffing
fixtures.

our engineering rules"scoring algorithm" as an ADR trigger. This is
that ADR.

## Decision

We introduce a new package `engine/scoring/` with four small modules
plus a lifecycle hook:

1. **`engine/scoring/model.py`** owns the math. The eight the documentation axes — `functional`, `security`, `performance`, `accessibility`, `api`, `visual`, `llm_audit`, `flake_risk` — are computed independently: - For each non-flake axis, the component score equals `max(0, 100 - Σ severity_penalty(finding) for finding in axis)`. - The flake-risk axis reads `flake_rate` off each `ModuleResult.metrics`, averages, and converts to `100 * (1 - min(1, avg / policy.max_flake_rate))`. Modules with no `flake_rate` metric default to 100 (no flake observed). - The aggregate `total` is the weighted average of the eight axes clamped to `[0, 100]`. Default weights match the documentation (functional 30 / security 20 / performance 15 / accessibility 10 / api 10 / visual 5 / llm*audit 5 / flake_risk 5). - Per-severity penalties default to the midpoint of the the documentation ranges (high 17.5, medium 6.5, low 2.0). Critical is fixed at 30 so the numeric score still reflects severity even when `policy.block_on_critical` is the dominant signal. The three midpoints are exposed as `policy.severity_penalty*\*` config keys for projects that want stricter or looser per-finding penalties.

2. **`engine/scoring/blockers.py`** applies the structural blocker rules from our engineering rules: - `critical_finding` — any critical finding when `policy.block_on_critical`. - `security_high` — any high-severity finding in the `security` module when `policy.block_on_high_security`. - `p0_flow_failed` — any failed P0 functional flow (detected via the `@p0` tag in the finding title; see the MVP note below). - `too_many_p1_failures` — more than `policy.max_failed_p1_flows` P1 flows failed (structural rule; not tied to a single `finding_id`).

3. **`engine/scoring/decision.py`** translates the score + blockers + run status into a `PolicyDecision`. Priority (top wins): unsafe → incomplete/dry-run (`inconclusive`) → blockers (`blocked`) → score below `policy.min_quality_score` (`blocked`) → any medium finding (`pass_with_warnings`) → otherwise `pass`.

4. **`engine/scoring/policy_gate.py`** glues the three together via `apply_policy_gate(...)` and registers the two lifecycle hooks `_score_hook` (CALCULATE*QUALITY_SCORE) and `_gate_hook` (APPLY_QUALITY_GATES). The score hook derives an \_effective* status from `module_outcomes` (any errored → incomplete → inconclusive) because `LifecycleContext.status` is not finalized until `generate_reports`. The gate hook flips `quality_gate_passed = False` only when the decision is `blocked`; `_finalize_status` then stamps `failed`.

5. **`sentinel report --explain-score`** (replaces the Phase-15 stub for the explain path only) renders the math behind a completed run's `score.json`. It prints per-axis contributions, severity penalties, blockers, and policy thresholds, and writes a deterministic `score-explanation.md` next to the source `score.json`. Calling `sentinel report` without `--explain-score` still surfaces a "lands in Phase 15" error (exit 7) — no fake completion (CLAUDE §37).

### P0 / P1 priority detection — MVP note

The `Finding` model does not yet carry a `priority` field. Phase 10
embeds the priority tag (`@p0..p3`) in the test name, which becomes
the `Finding.title`. The Phase-14 `finding_priority(finding)` helper
parses that tag out of the title (falling back to the description).
This is a deliberate MVP shortcut: when a future phase unifies
priority signalling on the Finding model itself, the helper switches
to that field without changing the public scoring contract.

## Consequences

- **Positive.** The score is a pure function of typed inputs + policy config. The reproducibility test (`tests/property/scoring/test_reproducibility.py`) asserts byte equality across 5000 hypothesis-generated input vectors. The replay test (`tests/integration/scoring/test_replay.py`) holds three canonical input fixtures against committed expected `score.json` bytes — any drift in the scoring math fails CI immediately.
- **Positive.** Every decision priority (unsafe → incomplete → blocked → below-threshold → warnings → pass) is observable: the `PolicyDecision.reasons` tuple captures the rule(s) that fired. The CLI explainer renders that narrative in human + JSON + Markdown.
- **Negative / trade-off.** P0 / P1 detection relies on the title containing the `@p0` / `@p1` tag. Modules outside Phase 10 that emit functional-priority findings must either include the tag in the title or wait for the unified priority field.
- **Negative / trade-off.** Findings whose module name is outside the `COMPONENT_AXES` tuple (e.g. a third-party plugin emitting a `compliance` module) only affect the severity-penalty bookkeeping; they do not yet lower any component score. Phase 24 (plugin architecture) will introduce a way for plugins to declare which axis they contribute to.
- **Follow-up obligations.** When Phase 10/24 land richer priority / axis signalling, retire the title-based fallback and add the new field to the Finding schema (with a SCHEMA_VERSION bump).

## Alternatives considered

- **Hand-coded score in each module.** Rejected: scoring drifts per-module and reproducibility becomes a coordination problem. our product spec wants one global score, derived in one place.
- **Severity penalties as fixed constants.** Rejected: the documentation specifies _ranges_, and users have legitimate reasons to be stricter (regulated environments) or looser (early-stage exploration). Three optional fields on `PolicyConfig` give the knobs without adding a per-module override mess.
- **Stamp the decision earlier (during `run_modules`).** Rejected: the lifecycle's status is intentionally finalized in `generate_reports` so the run record reflects every signal, including downstream module-error categorization. The scoring hook reads `module_outcomes` directly to derive an effective status without depending on the lifecycle's stamping order.

## References

- PRD section(s): our product spec (Quality Scoring Model), §13.2 (Exit codes), §17.1 (Configuration), §20 (Evidence & Reporting).
- our engineering rules rule(s): our engineering rules(Quality score rules), §39 (CI rules), §34 (ADR triggers), §37 (No fake completion).
- Related ADRs: ADR-0008 (Report schemas & reporter pipeline), ADR-0013 (Runner architecture), ADR-0015 (Module contract).
