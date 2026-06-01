# ADR-0024: LLM-Code audit module — heuristics, signal contract, report differentiator

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

the documentation names the LLM-Code audit as one of SentinelQA's core
differentiators (§28). The audit hunts for the specific failure modes
characteristic of LLM-generated applications: dead buttons, fake
routes, mock data shipped to production, forms without working
submit, missing CRUD edges, UI-only authorization gates, hardcoded
credentials, secrets stored in browser storage, missing loading and
error UI, frontend/backend validation mismatch, "coming soon"
placeholders leaked into flows, and console errors the UI silently
ignores.

We have two structural choices:

1. **Browser-driven.** Spin up Playwright, exercise each route, watch the network, dump storage, intercept console output. Highest fidelity but adds a second runner harness, doubles wall-clock for `sentinel audit`, and tightly couples the audit to / 08 runtime.
2. **Signal-driven.** Consume what earlier phases already capture ( discovery output, optional runner evidence, optional source-root scan), plus a small set of HTTP probes the module can perform itself for fake-route and UI-only-auth checks. Lower wall-clock, no new harness, deterministic and hermetic test suite, but each check skips honestly when its signal isn't present.

the documentation leaves the implementation open. our engineering rules
completion: a check that emits success without evidence is worse than
a check that emits "skipped — no signal available." our engineering rules
forbids credential leakage anywhere in persisted output.

## Decision

We ship the LLM-Code audit as a signal-driven `SentinelModule`
(`modules.llm_audit.LlmAuditModule`, ADR-0015) that loads inputs from
known artifact paths and runs thirteen pure-Python checks over them.
Each check is a standalone function returning typed `CheckFinding`
records that consolidate into the documentation `Finding`s via
`modules.llm_audit.findings.findings_from_check_findings`.

Concrete decisions:

1. **Thirteen checks, one rule catalogue.** Sixteen stable `LLM-*` rule IDs live in `modules.llm_audit.rules`. Severity and confidence defaults are part of the catalogue; checks override per-finding only when a specific signal warrants it. Bumping a default severity or wording is a our engineering rules amendment.

2. **Pure-function checks.** Every check is `Iterable[X] →
tuple[CheckFinding,...]`. No I/O, no globals, no module state. This makes every check independently testable and keeps the module under 200 lines per check.

3. **Typed `LlmAuditInputs`.** A single dataclass enumerates every signal source. Missing signals (the runner never captured them, the source root wasn't supplied) leave the corresponding field empty; the matching check produces no findings, and the module's per-run `llm_audit/index.json` records `signal_available=false` so the audit trail is honest.

4. **Production wiring reads disk.** `modules.llm_audit.inputs.load_inputs` reads `discovery.json`, `api.json`, `forms.json` from the discovery artifact root, plus optional `signals.json` and `source_files.json` from `signals_root`. Malformed JSON, non-list sections, and bogus entries are dropped silently — the loader never throws, the module never crashes on user-provided input.

5. **Credential redaction is mandatory.** The hardcoded-credential scanner double-redacts every snippet: the matched span is replaced with `[REDACTED:hardcoded_credential]` before the line is passed through `engine.policy.redaction.redact`. Tests assert the literal never appears in any persisted finding.

6. **Status policy.** The module is `skipped` when no check had any signal, `failed` when any high/critical finding fires, `passed` otherwise. The CLI maps these to exit codes 0 (skipped or passed), 1 (high/critical present), 4 (unsafe target), 6 (module error), 7 (factory missing).

7. **Reporter differentiator.** A new context block (`build_template_context.llm_audit`) drives a dedicated "LLM-Code Audit" section in `report.html` and a Markdown table in the PR comment. The section appears only when the module ran OR produced findings — clean runs against an unrelated codebase stay silent so non-LLM workflows don't see an empty differentiator block.

8. **No new TS subcommand.** deliberately reuses existing signal sources (discovery output, optional runner artifacts) and adds nothing to `packages/ts-runtime`. If a future phase wants richer per-route browser instrumentation (long-task timing, storage dumps, console capture) it can extend the existing `sentinel-ts` reporter rather than spawning a parallel run.

## Consequences

- **Positive.** Audit runs in a few hundred milliseconds against a pre-discovered project, adds zero new TS deps, has a hermetic test suite (no Playwright/Chromium in unit/integration), and produces per-rule findings with our product spec evidence. Coverage gate ≥ 90 % per file is met (current ≥ 94 % across the package).

- **Negative / trade-off.** Some checks require runtime signals the default discovery + runner pipeline doesn't yet capture (browser storage dumps, console output post-auth, validation probes against malformed payloads). When those signals are absent the check reports `signal_available=false`; the audit answers honestly ("we didn't observe this dimension") rather than overclaiming.

- **Follow-up obligations.** (Healer) and (Chaos) can extend the captured signal set by emitting matching JSON payloads into `<run-dir>/llm_audit/signals.json`. No protocol or schema change is needed — the loader already ingests every section defined here. If/when a Phase-XX cleanup wants to remove the defensive `isinstance` branches in `inputs.py`, the schema would need to be locked under a wire-format ADR and validated up front.

## Alternatives considered

- **Browser-driven module.** Rejected: doubles wall-clock for `sentinel audit`, requires a second `sentinel-ts` subcommand for storage/console dumps, and ties LLM-audit to Chromium being installed even when the project ships a static-site fixture.

- **LLM-summarised audit.** Asking an LLM to grep the codebase for "smells" was rejected on three counts: deterministic results are preferable for release-confidence, vendor cost would apply per-run, and the failure mode (false positives in LLM summarisation) is exactly the failure mode the module is meant to catch.

- **One mega-check per audit.** Folding all signals into a single rule (`LLM-CODE-SMELL`) was rejected because the documentation enumerates the specific defects users should be able to triage independently; per-rule IDs let CI gates target individual defect classes (e.g. `LLM-UI-ONLY-AUTH` blocks; `LLM-PLACEHOLDER-TEXT` warns).

## References

- the documentation section(s): the documentation (LLM-Code audits), §28 (Differentiation), §20 (Evidence).
- our engineering rules rule(s): our engineering rules(Module contract), §24 (Findings), §31 (LLM-Code Audit Rules), §33 (Logging/Secrets), §37 (No placeholder completion).
- Related ADRs: ADR-0015 (`SentinelModule` contract), ADR-0008 (Report schemas), ADR-0018 (Security module — gated probes, applied here for hardcoded credential scanning).
