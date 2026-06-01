# @sentinelqa/ts-runtime

Status: `Experimental` — Phase 04 in flight ().

The TypeScript half of SentinelQA. Python (`engine/`) orchestrates; this
package launches Playwright, runs spec files, captures evidence
(trace / screenshot / video / HAR / DOM / console / network), and emits
structured JSONL events back to Python over `stdout`.

## Contract with Python

The Python ↔ TypeScript contract is defined by:

- The JSON Schema at `packages/shared-schema/ts-events.schema.json` (every event SentinelQA emits, versioned via `schema_version`).
- ADR-0009 (Python ↔ TS protocol) — rationale + change procedure.
- `engine/orchestrator/ts_bridge.py` — Python-side parser.

If either side drifts from the schema, the parity tests
(`tests/integration/protocol/test_parity.py` and the TS equivalent)
fail in CI. Bump `schema_version` and write a migration ADR — never
silently rename a field.

## Public surface (per `package.json` exports)

- `@sentinelqa/ts-runtime` — package identity, redaction helpers, event emitter / parser.
- `@sentinelqa/ts-runtime/playwright` — `sentinelTest`, `sentinelStep`, `captureEvidence`, `redactedNetwork`.
- `@sentinelqa/ts-runtime/protocol` — JSONL event types, emitter helpers.
- `@sentinelqa/ts-runtime/locators` — semantic-first locator chain, brittleness audit (consumed by Phase 07 / Phase 20).

## Binary

`sentinel-ts` (resolved to `dist/cli.js`) is the executable Python
spawns. Today only `--help` / `--version` are wired; `run`,
`list-tests`, `validate-helpers` exit 7 with a "lands in Phase 04.03"
message(no fake completion).

## Build & test

```bash
pnpm --filter @sentinelqa/ts-runtime build # emits dist/
pnpm --filter @sentinelqa/ts-runtime typecheck # tsc --noEmit
pnpm --filter @sentinelqa/ts-runtime test # vitest
node packages/ts-runtime/dist/cli.js --version
```

## Safety boundary (our engineering rules §6 / our product spec)

This package never imports stealth, evasion, fingerprint-spoofing,
CAPTCHA-bypass, or proxy-rotation libraries. Locator strategy is
semantic-first (`getByRole`, `getByLabel`, …) per our engineering rules §21 — no
brittle CSS unless no semantic option exists, and never `wait_for_timeout`
in generated tests.
