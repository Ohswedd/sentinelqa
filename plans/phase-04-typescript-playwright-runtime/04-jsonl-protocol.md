# Task 04.04 — Python ↔ TS JSONL protocol

## Objective

Define and version the JSONL event protocol that the TS runtime emits and Python parses. Lock it in `packages/shared-schema/` so both sides validate against the same source of truth (CLAUDE §8).

## Deliverables

- `packages/shared-schema/ts-events.schema.json` — JSON Schema (draft 2020-12) listing every event:
  - `run.start`, `run.end` — run id, target, started/finished, status.
  - `test.start`, `test.end` — test id, title, file, durationMs, status, retries, error.
  - `step.start`, `step.end` — step name, durationMs, ok, error.
  - `evidence` — type, path, label, related test/step id.
  - `network.request`, `network.response` — redacted url, method, status, durationMs, content-length, content-type.
  - `console` — level, message (redacted), source.
  - `dom.snapshot` — path, label.
  - `module.event` — generic module hook (used by Phase 11+ to emit per-module signals).
  - `log` — structured log (level, msg, fields), redacted.
  - `error` — top-level error event (code, message, stack? redacted).
- Each event includes: `schema_version` (string), `seq` (monotonic int from start of run), `ts` (RFC 3339 UTC).
- Python parser: `engine/orchestrator/ts_bridge.py` exposing `parse_event(line: str) -> Event` (Pydantic model), `stream_events(stdout) -> AsyncIterator[Event]`.
- TS emitter helper: `packages/ts-runtime/src/protocol.ts` with typed factories `emit({ type: "step.end", ... })` that bump `seq` and write to stdout.
- Cross-language tests: a fixture file `tests/golden/ts-events/sample.jsonl` parsed by both Python and TS; mismatches fail CI.

## Steps

1. Author the schema; validate it.
2. Build the Python parser with Pydantic discriminated unions on `type`.
3. Build the TS emitter; generate types from the JSON Schema at build time (`json-schema-to-typescript`).
4. Write parity tests.

## Acceptance criteria

- Both sides emit/parse the same JSONL.
- A deliberate field rename in the schema fails CI in both languages.
- Schema version bumps cause an explicit migration ADR.

## Tests required

- `tests/integration/protocol/test_parity.py` (Python).
- `tests/integration/protocol/parity.test.ts` (TS).

## PRD / CLAUDE.md references

- PRD §11 Architecture.
- CLAUDE.md §8 Runtime ownership.

## Definition of Done

- [ ] Schema + parser + emitter + parity tests committed.
- [ ] ADR-0009 finalized.
- [ ] `STATUS.md` updated.
