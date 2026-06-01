# ADR-0009: Python ↔ TypeScript JSONL protocol and TS runtime boundary

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

our engineering rules
responsibilities: Python is the orchestration, configuration, scoring,
and reporting brain; TypeScript is the Playwright-facing runtime that
launches browsers and observes execution. The two runtimes must
communicate over an explicit, machine-readable boundary — without one,
"hidden coupling" creeps in and every Phase
05+ module would invent its own wire format.

Phase 04 builds that boundary. We needed to decide:

1. **Where does the boundary live?** Process-level (subprocess + pipes) vs. shared library / FFI.
2. **What is the wire format?** Free-form `console.log` strings, JSON-RPC, raw stdout, or line-delimited JSON.
3. **What is the schema authority?** Python source-of-truth, TS source- of-truth, or a shared schema in `packages/shared-schema/`.
4. **How does the TS runtime tell Python it failed?** Exit codes, in-stream events, or both.
5. **How do we keep the two halves in sync over the project's life?**

Hidden constraints (the documentation, our engineering rules§33):

- The TS runtime must never re-implement redaction; the Python rule set is the source of truth. Drift here is the highest- blast-radius failure mode in the project.
- Every Playwright event must be auditable from Python . That means: typed Pydantic models on the Python side, schema validation in CI, byte-stable goldens.
- The boundary must support `--ci` mode where the stdout pipe carries ONLY structured events — no chatter, no spinners (our engineering rules/§39).

## Decision

We adopt a process-level boundary with line-delimited JSON over the
child's stdout, governed by a single JSON Schema in
`packages/shared-schema/`. Concretely:

1. **Process model.** Python spawns `sentinel-ts` (the bin in `packages/ts-runtime/dist/cli.js`). The TS process is responsible for invoking Playwright and translating its callbacks into SentinelQA events. Python parses the JSONL stream live (`stream_
events` in `engine/orchestrator/ts_bridge.py`).
2. **Wire format.** Line-delimited JSON. Every event carries the envelope `{type, schema_version, seq, ts}` plus a `type`-specific payload. The discriminator is `type`; both halves use the same fourteen kinds: `run.start`, `run.end`, `test.start`, `test.end`, `step.start`, `step.end`, `evidence`, `network.request`, `network.response`, `console`, `dom.snapshot`, `module.event`, `log`, `error`.
3. **Schema authority.** `packages/shared-schema/ts-events.schema.json` (Draft 2020-12). The TS emitter writes against it; the Python parser is hand-aligned and CI verifies both halves accept the same fixture (`tests/golden/ts-events/sample.jsonl`). Same pattern as `packages/shared-schema/redaction-rules.json`: Python owns the canonical rule set and TS mirrors it from the exported JSON; CI's `--check` mode is the single drift gate (`scripts/export-
redaction-rules.py`).
4. **Versioning.** `PROTOCOL_VERSION` is a string constant in both languages. The Python parity test grep-asserts the TS constant matches. A schema change requires bumping `PROTOCOL_VERSION` and landing a new ADR (this ADR's successor). Within a major version, additive fields are allowed and Python's parser ignores unknown keys at the envelope; required-field drift is the failure mode the parity test catches.
5. **Exit codes.** `sentinel-ts run` returns 0 (all pass), 1 (≥1 test failed/timed out), 2 (Playwright crashed / config invalid / spawn failed), 7 (sync dispatch hit an async command — programmer error). These map to the documentation / CLAUDE §13's exit-code grid.
6. **Reporter wiring.** A Playwright `--reporter=<path>` plugin (`packages/ts-runtime/src/reporter.ts`) translates Playwright's callbacks (`onBegin`, `onTestBegin`, `onStepBegin`, `onStepEnd`, `onTestEnd`, `onEnd`) into our events. `printsToStdio: true` so Playwright suppresses its own default reporter output and our JSONL stream stays clean.
7. **Package layout.** A single workspace package (`@sentinelqa/ts-runtime`) owns three subpath exports (`./protocol`, `./playwright`, `./locators`) so Phase 07 (Generator) and Phase 20 (Healer) consume only what they need without dragging in the runner CLI. The single-package decision (rather than a split `@sentinelqa/playwright-helpers`) keeps the build pipeline / typecheck / vitest config single-source.
8. **Redaction symmetry.** Every event payload passes through the redaction layer **before** emission. The TS layer (`packages/ts-runtime/src/redact.ts`) loads `packages/shared-schema/redaction-rules.json` at module init; CI re-runs `scripts/export-redaction-rules.py --check` and a 19-record byte-parity fixture proves the two implementations agree on strings / dict values / headers (URL byte-form parity is out of scope — URL class lowercases the hostname, the behaviour is tested separately).

## Consequences

**Positive:**

- A future Phase 08 (Runner) consumes one async-iterable surface (`stream_events`) and doesn't need to know about Playwright at all.
- Schema drift fails CI in both languages: the meta-schema check validates the schema file, the parity fixture validates each line, and the cross-language parity test asserts both parsers agree.
- The JSONL boundary plays nicely with `--ci` mode: stdout carries ONLY structured events; we never write progress chatter that would break the Python parser.
- Adding new event kinds is additive — bump the schema, add the Pydantic model + a TS event interface, regenerate the parity fixture.

**Negative / trade-off:**

- Two implementations of redaction (one in Python, one in TS) — but the drift gate plus the byte-parity fixture make this safe. The alternative (calling Python from TS or vice versa per-line) added unacceptable latency to every Playwright event.
- The JSONL stream cannot carry binary attachments inline; the Reporter writes paths and Playwright writes the bytes to disk. This matches our product spec's "every finding has reproducible evidence" model but means Python must be able to read the run-dir on the same filesystem as the TS process — fine for local + most CI lanes, needs revisiting if/when remote-execution lands (out of scope for Phase 04).

**Follow-up obligations:**

- Phase 08 (Runner) wires `sentinel-ts run` into the run lifecycle and starts feeding stdout into `stream_events`.
- Phase 14 (Quality Scoring) and Phase 15 (HTML & JSON Reports) treat the JSONL stream as the canonical source for test outcomes — no parallel "real" reporter.
- Phase 18 (MCP & Agent Interface) re-exports the event types as agent messages; any rename there must propagate to this schema.
- Any future protocol bump writes a successor ADR and updates both `PROTOCOL_VERSION` constants in the same PR.

## Alternatives considered

- **JSON-RPC over stdio.** Rejected: request/response semantics don't match the "Playwright tells us, we observe" data flow; introduces RPC framing overhead for every step event.
- **gRPC / Unix domain socket.** Rejected: cross-platform pain (Windows), runtime/protobuf dependency, vastly more complex versioning for a problem that doesn't need bi-directional streaming.
- **Free-form `console.log` strings parsed by regex.** Rejected on CLAUDE §38 grounds: machine-readable reports must be schema-stable and versioned. Regex-on-string is the opposite.
- **Single Python process driving Playwright via `playwright-python`.** Rejected: doubles the source of truth (now both `playwright-python` and `@playwright/test` need to agree on locator semantics), and the Healer (Phase 20) wants to consume Playwright's accessibility snapshot API which is more mature in the TS runtime.
- **Split `@sentinelqa/playwright-helpers` package.** Rejected as premature: a second workspace package doubles the build/test/lint surface for no consumer the project ships in Phase 04. Re-evaluate if/when Phase 07's Generator wants its own helper subset.

## References

- PRD section(s): the documentation Runner, §11 Architecture, §15 TS Runtime, §20 Evidence and Reporting.
- our engineering rules rule(s): our engineering rules§8 Runtime ownership, §11 Artifact and data rules, §13 CLI rules, §21 TS / Playwright rules, §33 Logging and secrets, §39 CI.
- Schema files: - `packages/shared-schema/ts-events.schema.json` - `packages/shared-schema/redaction-rules.json`
- Code: - `packages/ts-runtime/src/protocol.ts` (TS emitter + parser) - `engine/orchestrator/ts_bridge.py` (Python parser) - `packages/ts-runtime/src/reporter.ts` (Playwright → JSONL) - `packages/ts-runtime/src/runner.ts` (spawn + lifecycle)
- Fixtures: `tests/golden/ts-events/sample.jsonl`, `tests/golden/redaction/parity.json`.
- Related ADRs: ADR-0007 (Run lifecycle), ADR-0008 (Report schemas).
