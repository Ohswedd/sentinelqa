# ADR-0025: Healer / Self-Repair — deterministic proposals, banner-aware apply, assertion-weakening guard

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

the documentation names the Healer as a core module. our engineering rules
the constraint: repairs are conservative, every proposal carries
confidence + reason + evidence + a `requires_human_review` flag,
assertions cannot be weakened silently, hand-edited specs cannot be
overwritten. the documentation names the `sentinel fix` CLI surface.
the documentation (Phase 18) already shipped `sentinel.verify_fix` as the
agent-observable confirmation loop — but only as the verifier; the
Healer's apply-fix logic was deferred to Phase 20.

We have three structural decisions to make:

1. **Where the Healer runs.** Inline inside the Analyzer (Phase 09) or as a separate facade the Analyzer routes to?
2. **What backs the repair search.** A browser-driven exploratory pass, or a deterministic algorithm over already-captured signals (descriptor + DOM map + spec source)?
3. **How `sentinel fix` decides to apply.** Defaults that lean permissive ("just apply the high-confidence ones") or defaults that lean conservative ("review-only unless the operator opts in")?

our engineering rules(3): conservative. The
Healer never mutates app code, never weakens assertions silently,
never touches hand-edited files.

## Decision

We ship Phase 20 as a deterministic, signal-driven module under
`engine/healer/`. Concretely:

- **Facade.** `engine.healer.Healer.propose(failure, inputs, *, context)` returns a tuple of typed :class:`RepairProposal` records. It does not write to disk, does not decide whether a proposal applies, and does not know about the run lifecycle. The Analyzer publishes `is_healer_candidate(result)` (Phase 09's `AnalyzerResult.classification.category == "test_bug"` with confidence ≥ 0.5) so the calling layer (CLI / SDK) knows when to invoke the Healer.

- **Three deterministic proposers.** - `propose_locator_repair`: scores `DomCandidate` records against a `LocatorDescriptor` snapshot (`role` / `accessible_name` / `landmarks`). Exact role + name + landmark → 0.95. Same role + name (different landmark) → 0.9. Fuzzy name match (string similarity ≥ 0.8) → 0.70..0.75. Role-only → 0.5. - `propose_wait_repair`: detects `await page.waitForTimeout(...)` (forbidden by our engineering rules) and proposes deletion. Confidence 0.9 when the next assertion is `toBeVisible` / `toHaveText`; 0.6 for other matchers; 0.3 when no following assertion anchors an explicit wait. - `propose_fixture_repair`: turns "seeded record missing" (0.85 confidence) or "API contract drifted" (0.7 confidence) into structured proposals whose `proposed_change` is the shell command to run, not a code edit. The Healer never mutates a database.

- **Wire format.** `RepairProposal` extends the Phase-01 domain `RepairSuggestion` envelope. Schema locked at `packages/shared-schema/repair-proposal.schema.json` (Draft 2020-12). Persisted under `<run-dir>/healer/<id>.json` plus an aggregate `index.json`. `RPR-*` is a registered entity prefix (`engine.domain.ids.ENTITY_PREFIXES`).

- **Banner-aware apply.** `engine.healer.banner.detect_banner_status` inspects the head of a spec for the Phase-07 banner (`// SENTINELQA AUTO-GENERATED`) and a `// generated_at:` timestamp. Missing banner → hand-edited. Banner present but file mtime is more than 5s after the recorded `generated_at` → hand-edited. Hand-edited specs are refused regardless of mode.

- **Auto-apply gating.** `engine.healer.gating.decide_auto_apply` combines three operator postures (`policy.healer.auto_apply` is `off` / `safe` / `aggressive`), the banner status, the proposal's `requires_human_review` flag, and the confidence threshold to return one decision: should apply, with a one-sentence reason. Defaults: `auto_apply: off`, `auto_apply_threshold: 0.9`.

- **Assertion-weakening guard.** `engine.healer.diff.assert_no_assertion_weakening` counts structural Playwright assertions in original vs proposed (`expect(`, `.toBe*`, `.toHave*`, `.toEqual`, `.toMatch`, `.toContain`) after stripping `//` line comments and `/* ... */` block comments. Any decrease raises `AssertionWeakeningError` unless `allow_weaken=True`. Locator and wait proposers call the guard unconditionally; assertion-stabilization proposers (Phase 20+) must call with `allow_weaken=True` and the CLI must log the override in the audit log.

- **CLI.** `sentinel fix` replaces the Phase-02 stub. Options: `--latest / --no-latest`, `--run RUN-...`, `--apply none|safe|aggressive`, `--dry-run`, `--allow-weaken`, `--review-only`, `--threshold 0.5..1.0`. Default mode is `--apply none` — review-only. Every applied repair writes an `audit.log` `healer.apply` line with the gating decision reason verbatim. Exit codes: 0 / 2 / 6.

- **MCP integration.** `sentinel.suggest_fix` now surfaces persisted healer proposals for the finding's target file in addition to the module's `recommendation` / `suggested_fix`. `sentinel.verify_fix` (Phase 18, ADR-0023) already confirms the agent's apply through re-running the audit; Phase 20 wires the loop end-to-end without changing the wire envelope.

- **No runner harness.** The Healer is pure-Python over already captured signals. No new Playwright invocation, no new TS subcommand. The descriptor and DOM-candidate inputs are consumed from Phase 04 (`describeLocator`) and Phase 05 (discovery DOM map) outputs.

- **Config block.** `healer.auto_apply` ∈ {`off`, `safe`, `aggressive`} default `off`. `healer.auto_apply_threshold` ∈ [0.5, 1.0] default `0.9`.

## Consequences

- **Positive:** - Deterministic by construction. Same descriptor + same DOM candidates + same spec → byte-identical proposal stream. - Safe by default. `--apply none` is the default; `--apply safe` refuses assertion changes; assertion changes require both `--apply aggressive` AND `--allow-weaken`. - Hand-edited specs are detectable from the file alone (banner absence or mtime drift) — no git interaction required. - The wire format is independently versioned at the top level (`packages/shared-schema/repair-proposal.schema.json`, schema_version `1`) so the HTML report and the CLI can both validate the artifact without reaching into the Phase-01 domain schema. - The assertion-weakening guard is a standalone function called by every proposer plus the test sweep, so the invariant cannot be quietly bypassed in a future repair kind.

- **Negative / trade-off:** - The Healer's "DOM candidates" must be harvested by the caller (Phase 05 discovery or a Phase 04 helper) — we don't ship a "rerun the page and observe" code path in Phase 20. - The fixture proposer only emits human-actionable shell commands (e.g. `pnpm seed`); it cannot resolve the situation on its own. That's intentional (our engineering rules: data mutations require human review) but it means CI agents can't fully unblock themselves from data drift. - The banner mtime check uses a 5-second skew tolerance; coarse file systems may still produce false positives. We accept that over the noisier alternative (e.g. SHA-of-prior-content embedded in the banner).

- **Follow-up obligations:** - When the assertion-stabilization proposer ships (out of scope for Phase 20), it must call the assertion-weakening guard with `allow_weaken=True` AND the CLI must require `--allow-weaken`. A test enforces the guard's structural invariant. - The "rerun the page to harvest DOM candidates" code path is a future Healer enhancement, not a Phase-20 promise.

## Alternatives considered

1. **Inline Healer inside the Analyzer.** Rejected: the Analyzer is a pure-function pipeline over `FailureSignal`s; Healer needs DOM candidates, spec source, banner status — all I/O concerns that should live one layer up.
2. **Browser-driven repair.** Rejected for the MVP: doubles the wall-clock of `sentinel fix`, requires a second runner harness, tightly couples the Healer to Phase 04 / Phase 08 runtime, and doesn't materially improve the deterministic case. We can add a "rerun and harvest" backend later behind the same `propose()` facade if needed.
3. **Apply diffs with `patch(1)`.** Rejected for portability: the `patch` binary's behavior varies across distributions and is absent on Windows by default. We do a direct string substitution instead since every Phase-20 proposal is a single-line replacement.

## References

- the documentation Healer module
- the documentation Failure repair workflow
- the documentation LLM agent workflow
- the documentation CLI Specification
- the documentation MVP delivery (Phase 18 verify_fix)
- the documentation Finding schema (evidence requirement)
- our engineering rules
- our engineering rules(audit log)
- our engineering rules
- our engineering rules/ Playwright rules (no arbitrary waits)
- our engineering rules-healing rules
- our engineering rules
- our engineering rules(ADR triggers)
- Related ADRs: ADR-0007 (Run lifecycle), ADR-0008 (Report schemas), ADR-0012 (Generated test conventions — banner), ADR-0014 (Analyzer rules — Healer routing), ADR-0021 (Public SDK surface), ADR-0023 (MCP — verify_fix decision matrix).
