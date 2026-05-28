# ADR-0017: Performance module — synthetic page/API/CPU/leak budgets

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

PRD §10.5 enumerates the performance capabilities SentinelQA must ship:
page-level Core Web Vitals budgets (LCP/CLS/INP), Time-to-First-Byte,
API endpoint latency budgets, JS bundle size, CPU blocking detection,
and repeated-navigation stability for memory-leak heuristics.

CLAUDE §27 is load-bearing: results must be explicitly labelled
**synthetic**. They are lab measurements collected in a headless
Chromium tab — they are reproducible and useful for catching
regressions, but they are not Real-User Monitoring. Every product
output the module emits must say so or invite the wrong interpretation.

The first SentinelQA module that drives a non-Playwright-spec runner is
the accessibility module (ADR-0016). Performance fits the same shape:
checks are per-route, the runner needs to inject PerformanceObservers
into a live browser, and there is no `TestExecution` analogue. We
reuse the runner-Protocol pattern rather than bending the Phase 08
runner.

## Decision

We introduce a dedicated runner abstraction for performance and a new
`sentinel-ts audit-perf` subcommand:

1. **Module shape.** `modules.performance.PerformanceModule` inherits
   from `engine.modules.base.SentinelModule` and follows the seven-step
   lifecycle (CLAUDE §9). `execute()` calls an injected
   `PerformanceRunner` instead of the Phase-08 Playwright runner. The
   runner returns a typed `PerformanceRunOutcome`; `emit_findings()`
   translates each `PerformancePageResult` via
   `modules.performance.findings.findings_from_pages`.
2. **Per-check evaluators.** Each PRD §10.5 capability is owned by a
   small deterministic Python evaluator:

   - `modules.performance.page_budget.evaluate_page_budgets` — median
     of N samples per metric (LCP/TTFB/INP/CLS) checked against
     `PerformanceBudgets`.
   - `modules.performance.api_latency.evaluate_api_latency` — P50/P95
     per templated endpoint, with `min_samples=5` so noisy P95s with
     ≤4 observations don't fire.
   - `modules.performance.bundle_cpu.{evaluate_bundle_size,
evaluate_long_tasks}` — totals (KB / blocking ms) compared
     against budgets.
   - `modules.performance.nav_stability.{summarise_nav_samples,
evaluate_nav_stability}` — first-to-last percentage growth on JS
     heap + DOM-node count.

   The Python side is the canonical normaliser: the findings layer
   never re-derives policy from raw browser output.

3. **Runner abstraction.** `PerformanceRunner` is a `Protocol` with a
   single method `run(invocation: PerformanceInvocation) ->
PerformanceRunOutcome`. Production uses `LocalPerformanceRunner`,
   which spawns `sentinel-ts audit-perf --input <run-config>.json` via
   `subprocess.run` and reads the artifacts the TS subcommand writes
   under `<run-dir>/perf/`. Tests inject `StubPerformanceRunner` to
   avoid Playwright + Chromium dependencies.
4. **TS subcommand.** `sentinel-ts audit-perf --input <path>` reads a
   deterministic JSON config (routes plus samples plus
   repeated_nav_samples plus budget timings), launches Chromium via
   `@playwright/test`, collects N samples per route, performs the
   N-visit repeated-nav loop, and writes one `<route-slug>.json` per
   route plus a top-level `index.json`. The launcher is injectable so
   vitest tests run without a real browser.
5. **Per-route artifact schema.** The envelope carries
   `schema_version: "1"` (constant `PERF_RESULT_SCHEMA_VERSION` on
   both runtimes). Future breaking changes bump this constant.
6. **CLI.** `sentinel perf` replaces the Phase 02 stub and runs the
   canonical `RunLifecycle` restricted to the `performance` module.
   Options: `--url / --routes / --samples / --repeated-nav-samples /
--discovery`. Exit codes: 0 (no high/critical findings), 1 (quality
   gate failed), 2 (config / CLI usage error), 4 (unsafe target),
   5 (sentinel-ts binary missing), 6 (runner failure).
7. **CLAUDE §27 wording guard.** Every finding description begins
   with "Synthetic performance check". A grep test
   (`tests/security/test_synthetic_perf_labeling.py`) forbids stronger
   claims ("Real-User Monitoring data captured", "RUM data captured",
   "field telemetry captured", "production user telemetry"). The
   negation phrase "not Real-User Monitoring data" appears in finding
   descriptions to actively warn the reader — that is allowed.
8. **Severity policy.** Page-budget and CPU-blocking exceedances are
   `high` when overage > 50 %, otherwise `medium`. Bundle-size
   violations follow the same rule. API-latency P95 violations are
   `medium` by default and escalate to `high` only when overage
   exceeds 100 % (one slow endpoint rarely blocks release on its own).
   Nav-stability findings are always `low` with confidence `0.5` —
   they are heuristics (CLAUDE §27); Phase 14 should not over-block on
   this signal.

## Consequences

- **Positive:**
  - Performance module follows the same `SentinelModule` contract as
    `FunctionalModule` and `AccessibilityModule` — orchestrator,
    audit log, and exit-code grid all work unchanged.
  - The runner abstraction keeps the Python side fully testable
    without Chromium. Heavy Playwright tests are gated by
    `SENTINELQA_HAS_CHROMIUM=1` on the TS side (consistent with
    Phase 04 / 10 / 11 fixtures).
  - The TS subcommand is a small, focused unit — the orchestrator
    accepts an injected launcher so vitest covers the full dispatch
    path with deterministic stubs.
  - Each evaluator is a pure Python function that takes the wire
    model + config and returns typed violations. Unit tests pin the
    rules per metric without spawning anything.
- **Negative / trade-off:**
  - Synthetic measurements are a proxy for real-user release
    confidence. The CLAUDE §27 wording guard mitigates the risk that
    consumers misread our findings as RUM data.
  - The repeated-navigation heuristic catches some leaks but is noisy
    on its own. Confidence is intentionally 0.5 so Phase 14 can
    weight it appropriately; the title says "potential memory leak"
    and the description explicitly calls it a heuristic.
  - `performance.memory.usedJSHeapSize` is Chromium-only. The TS
    runtime reports `memory_supported: false` on Firefox / WebKit;
    Python honours that flag and never raises memory findings
    without supporting samples.
- **Follow-up obligations:**
  - Phase 14 (Quality Scoring) reads the module weight + the
    severity-overage thresholds we set here. The PRD §19 grid is the
    source of truth there.
  - Phase 27 (Docs & ADRs) documents the explicit synthetic-vs-RUM
    distinction for users running `sentinel perf` against staging /
    production.

## Alternatives considered

- **Reuse Phase 08's Playwright spec runner.** Rejected: each
  capability would have to be expressed as a spec the generator
  hadn't seen, the runner would have to thread budget config through
  the test fixture, and per-route reports would be assembled from
  test-result fragments instead of typed wire models. The
  runner-abstraction path keeps each evaluator a pure function and
  preserves the same audit-log + lifecycle behaviour as Phases 10–11.
- **Use a third-party Lighthouse module.** Rejected: Lighthouse runs
  its own Chromium and Node controller, ships an opinionated scoring
  system, and bundles a UI we don't need. We would still have to
  translate its output to typed findings, and we lose direct control
  over the synthetic-vs-RUM wording.
- **Drop the per-route artifact and emit findings inline only.**
  Rejected for the same reason as ADR-0016: PRD §20 requires findings
  to carry reproducible evidence; the per-route JSON is exactly
  that evidence.
- **Drop the nav-stability heuristic in MVP.** Considered: it is a
  heuristic and noisy. Kept because it is one of the few signals
  SentinelQA can give for AI-generated apps that ship leaky useEffect
  cleanup or unbounded caches (PRD §10.9 ties heavily into this
  signal). Confidence is bounded to 0.5 to keep CI from over-blocking.

## References

- PRD section(s): PRD §10.5 (Performance testing), PRD §18.2
  (Finding schema), PRD §20 (Evidence & Reporting).
- CLAUDE.md rule(s): CLAUDE §9 (Module contract), CLAUDE §27
  (Performance rules — synthetic labelling), CLAUDE §11
  (Artifact tree).
- External: Core Web Vitals (web.dev), Long Tasks API
  (W3C), PerformanceObserver (MDN).
- Related ADRs: ADR-0015 (Module contract + functional module),
  ADR-0016 (Accessibility module — runner-abstraction pattern),
  ADR-0013 (Runner architecture — local + Docker).
