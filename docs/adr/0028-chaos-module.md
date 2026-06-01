# ADR-0028: Chaos module — Playwright-injected scenarios with JSONL bridge

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

ships the the documentation chaos / adversarial test module. the documentation
lists thirteen scenarios across four categories — network (slow_3g,
offline, api_500, api_timeout), session (expired token, missing
permissions), UX (duplicate submit, double-click race, back/forward,
refresh mid-flow), and data (empty dataset, large dataset, browser
storage corruption).

The module must satisfy three competing constraints:

1. **our engineering rules** Chaos scenarios must never give anyone a stealth / evasion / bot-detection-bypass capability. The thirteen the documentation scenarios are bounded UI / network injections — they exercise the _target's_ failure handling, never a third party.
2. **our engineering rules** The module follows the standard seven-step lifecycle so it composes with `sentinel audit`, `sentinel ci`, and the reporter / scoring stack without special cases.
3. **our engineering rules** Playwright instrumentation is TypeScript-owned (the chaos helpers are `page.route` / `goBack` / `setItem` callers); the Python side owns config, lifecycle, findings, and reports.

The cleanest split is the same one (a11y), (perf),
and (visual) use: TS-side helpers emit a typed event log;
the Python module ingests the log and turns observations into the documentation
§18.2 findings. There is no precedent in the repo for running a chaos
in-browser engine entirely from Python, and the alternative
(spawning a sidecar) would duplicate the bridge we already maintain.

## Decision

We ship the chaos module as a Python `ChaosModule(SentinelModule)`
backed by a TS chaos helper surface that emits the canonical
`ChaosEvent` JSONL.

**Wire format.** Each TS helper (`chaosNetwork`, `chaosSession`,
`chaosDuplicateSubmit`, `chaosEmptyDataset`, …) returns or appends a
`ChaosEvent` with shape:

```json
{
  "scenario_id": "network.api_500",
  "category": "network",
  "flow": "checkout",
  "observation": "no_error_state | uncaught_error |... | handled_gracefully",
  "route": "/api/checkout" // optional "detail": "...", // optional human note "evidence": { "console_lines": "3" } // optional flat str->str map
}
```

Events flow to `<run-dir>/chaos/events.jsonl`. The Python
`modules.chaos.ingestion` reader parses each line via Pydantic
(`extra="forbid"`), enforces an 8 MiB file-size cap, groups events
into `ChaosScenarioResult` records, and surfaces them through the
standard module lifecycle.

**Catalog.** `modules.chaos.scenarios.CATALOG` is the single source of
truth for both runtimes — thirteen entries mirroring the documentation. The
TS helpers use the same `scenario_id` strings; the Python ingestion
ignores events whose `scenario_id` is not in the catalog _only_ when
filtering, never when persisting them to the artifact tree (so the
audit log preserves what was thrown out).

**Safety boundary.**

- `modules.chaos` defaults `False`. The CI `nightly` preset flips it on; `fast` / `standard` / `full` do not.
- `ChaosConfig.api_timeout_abort_ms` clamps `[1_000, 120_000]` — there is no path to "hang forever" or to a sub-second hammer.
- `ChaosConfig.slow_3g_kbps` clamps `[100, 10_000]`. Below 100 Kbps the chaos helper _is_ a denial-of-service amplifier, which the engineering guidelines; above 10 Mbps the scenario is not "chaos" anymore.
- Session chaos uses Playwright `route` to rewrite outgoing `Authorization` headers. The TS helper never reads, persists, or re-signs production JWTs. `session.missing_permissions` requires the operator to supply a sandbox JWT (passed in opaque).
- No CLI flag named `--aggressive` / `--bypass` / `--stealth` / `--undetectable` / `--no-rate-limit` / `--ignore-robots` exists. `tests/security/test_chaos_no_evasion_flags.py` greps the package + CLI for forbidden literals and introspects the Typer parameters.

**Findings.** `modules.chaos.findings` maps each "bad" observation to
one of nine rule IDs:

| Observation                      | Rule ID                             | Severity |
| -------------------------------- | ----------------------------------- | -------- |
| `uncaught_error`                 | `chaos-uncaught-error`              | high     |
| `no_error_state`                 | `chaos-no-error-state`              | high     |
| `no_redirect_on_expired_session` | `chaos-session-expired-no-redirect` | high     |
| `no_graceful_permission_denial`  | `chaos-permission-missing-bad-ux`   | medium   |
| `duplicate_submit_accepted`      | `chaos-duplicate-submit-accepted`   | high     |
| `lost_form_state_on_navigation`  | `chaos-lost-form-state`             | medium   |
| `white_screen_on_refresh`        | `chaos-white-screen-on-refresh`     | high     |
| `missing_empty_state`            | `chaos-missing-empty-state`         | high     |
| `dom_explosion_on_large_dataset` | `chaos-dom-explosion`               | medium   |
| `crash_on_corrupted_storage`     | `chaos-crash-on-corrupted-storage`  | high     |

`handled_gracefully` never raises a finding.

## Consequences

- **Positive:** - The module reuses the JSONL bridge already shipped for a11y / perf / visual; there is one cross-runtime contract to maintain. - The module is testable without a real browser: every integration test we ship is fixture-driven (events JSONL in, findings out). - The catalog is centralized, so adding a fourteenth scenario is a one-file change (plus an ADR + the documentation update). - Findings flow through the standard scoring engine; nothing chaos- specific needs to land in.
- **Negative / trade-off:** - The Python module cannot, by itself, _cause_ a chaos scenario — it can only observe what the TS helpers wrote. That mirrors how a11y / perf already work and is acceptable, but it means operators must run the TS helpers via Playwright tests ( `sentinel test --module chaos`) to populate the event log. - The 8 MiB file-size cap means a runaway TS reporter that writes gigabytes is refused with `incomplete=true` instead of streamed — intentional, since memory bounding matters more than partial ingestion here.
- **Follow-up obligations:** - (plugin architecture) must ensure chaos scenarios can be added via plugins without forking `modules.chaos.scenarios`. - docs must surface the chaos scenario catalog so operators understand exactly what is bounded and what is not.

## Alternatives considered

1. **Python-only chaos via `httpx` / mitmproxy.** Rejected: the four UX scenarios (duplicate submit, double-click, back-forward, refresh mid-flow) and the storage-corruption scenario require a real DOM. A Python-only approach would silently skip them.
2. **Embed chaos as a sub-mode of the functional module.** Rejected: chaos has its own severity policy (e.g. `lost_form_state` is medium where a functional failure is always high) and its own off-by-default invariant. Folding the two would either weaken the chaos invariant or surprise functional users.
3. **Stream chaos events through the existing TS protocol bridge as `module_event` records.** Rejected: chaos events have a stable schema we own (catalog IDs, observation enum, evidence shape) and should not couple to the in-flight bridge schema. A dedicated `events.jsonl` keeps the schema versioned independently.

## References

- the documentation section(s): the documentation (Chaos / adversarial testing), §21.3 (CI modes — chaos in nightly).
- our engineering rules rule(s): our engineering rules(safety boundary), §9 (module contract), §10 (lifecycle), §29 (visual / chaos artifacts) — and §32 (typed errors).
- Related ADRs: ADR-0009 (TS↔Python JSONL bridge), ADR-0016 (a11y module), ADR-0027 (api testing module).
