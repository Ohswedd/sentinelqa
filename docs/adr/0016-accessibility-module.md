# ADR-0016: Accessibility module — axe-core + deterministic checks

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

the documentation enumerates the accessibility capabilities SentinelQA must
ship: axe-core integration, keyboard navigation, focus order, missing
labels, ARIA misuse, contrast, modal traps, form errors, landmark
structure, and screen-reader name detection. the engineering guidelines
load-bearing rule: outputs must never make a full-WCAG-compliance
claim — the product reports "Automated accessibility checks" only.

The first concrete `SentinelModule` ('s `FunctionalModule`,
ADR-0015) drives a Playwright spec set through the Phase-08 runner.
Accessibility is fundamentally different: checks are per-route rather
than per-spec, the runner needs to inject `axe-core` into a live
browser, and there is no `TestExecution` analogue. We need a second
runner shape that fits the module contract without bending the Phase
08 runner.

## Decision

We introduce a dedicated runner abstraction for accessibility and a
new `sentinel-ts audit-a11y` subcommand:

1. **Module shape.** `modules.accessibility.AccessibilityModule` inherits from `engine.modules.base.SentinelModule` and follows the seven-step lifecycle. `execute` calls an injected `A11yRunner` instead of the Phase-08 Playwright runner. The runner returns a typed `A11yRunOutcome`; `emit_findings` translates each `A11yPageResult` into the documentation findings via `modules.accessibility.findings.findings_from_pages`.
2. **Runner abstraction.** `A11yRunner` is a `Protocol` with a single method `run(invocation: A11yInvocation) -> A11yRunOutcome`. Production uses `LocalA11yRunner`, which spawns `sentinel-ts audit-a11y --input
<run-config>.json` via `subprocess.run` and reads the artifacts the TS subcommand writes under `<run-dir>/a11y/`. Tests inject `StubA11yRunner` to avoid Playwright + Chromium dependencies.
3. **TS subcommand.** `sentinel-ts audit-a11y --input <path>` reads a deterministic JSON config (routes + axe tags + budget timings), launches Chromium via `@playwright/test`, navigates each route in sequence, injects axe-core, runs the keyboard / landmark / accessible-name helpers (`packages/ts-runtime/src/a11y/*.ts`), and writes one `<route-slug>.json` per route plus a top-level `index.json` listing them. The launcher is injectable so vitest tests run without a real browser.
4. **Per-check helpers.** Each check is split into a small TS helper with a Python mirror under `modules.accessibility.checks/` so the deterministic rules (focus-trap detection, landmark policy, accessible-name fallback chain) are unit-testable on both runtimes. The Python side is the canonical normaliser — the findings layer never re-derives policy from raw axe output.
5. **Schema version.** The per-route JSON envelope carries `schema_version: "1"` (constant `A11Y_RESULT_SCHEMA_VERSION` on both runtimes). Future breaking changes bump this constant.
6. **the engineering guidelines** A grep test (`tests/security/test_no_wcag_compliance_claims.py`) scans the accessibility module + TS helper package for the phrases "fully WCAG compliant" / "WCAG compliant" / case variants. Any recurrence in product output fails CI.

## Consequences

- **Positive:** - Accessibility module follows the same `SentinelModule` contract as `FunctionalModule` — orchestrator, audit log, and exit-code grid all work unchanged. - The runner abstraction keeps the Python side fully testable without Chromium. Heavy Playwright tests are gated by `SENTINELQA_HAS_CHROMIUM=1` on the TS side (consistent with / fixtures). - The TS subcommand is a small, focused unit — the orchestrator accepts an injected launcher so vitest covers the full dispatch path with deterministic stubs.
- **Negative / trade-off:** - axe-core is **not** a workspace dependency. Projects that adopt SentinelQA's accessibility module install it themselves (`pnpm add axe-core`). The TS helper resolves it at runtime via `require.resolve('axe-core/axe.min.js')` and raises a typed `AxeCoreNotInstalledError` when the dep is missing. This keeps our lockfile minimal but pushes one install step onto users. - The accessibility module is the first that does NOT drive's runner. Future audit reports must handle the two shapes side-by-side (this is fine — `ModuleResult.metrics` is a free-form dict).
- **Follow-up obligations:** - (Quality Scoring) reads `policy.allow_medium_a11y` and the `accessibility` module weight — both already in the our product spec grid. - (Docs & ADRs) documents the explicit `pnpm add axe-core` requirement for users running `sentinel a11y` against real pages.

## Alternatives considered

- **Generate Playwright specs that each call `axe.run`.** Rejected: it forces the accessibility module to emit specs the Phase-07 generator hasn't seen, doubling the determinism work without making per-route reporting any easier. The runner-abstraction path also lets us add non-Playwright check engines later (e.g. `pa11y`) without re-wiring the module.
- **Bundle axe-core directly into `@sentinelqa/ts-runtime`.** Rejected: axe-core's ~600 KB tarball would bloat every dependent install even for projects that never run `sentinel a11y`. We prefer the runtime resolution + clear error message.
- **Drop the per-route artifact and emit findings inline only.** Rejected: our product spec requires findings to carry reproducible evidence; the per-route JSON is exactly that evidence.

## References

- the documentation section(s): the documentation (Accessibility testing), the documentation (Finding schema), our product spec (Evidence & Reporting).
- our engineering rules rule(s): the engineering guidelines(Module contract), the engineering guidelines(Accessibility rules — no full-compliance claims), the engineering guidelines(Artifact tree).
- External: axe-core (Deque) — <https://github.com/dequelabs/axe-core>.
- Related ADRs: ADR-0015 (Module contract + functional module), ADR-0013 (Runner architecture — local + Docker).
