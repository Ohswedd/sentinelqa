# Task 04.02 — `@sentinelqa/playwright` helpers

## Objective

Export the reusable helpers consumed by SentinelQA-generated tests (PRD §15.2): `sentinelStep`, `captureEvidence`, `redactedNetwork`, plus typed contexts that wrap Playwright's `test` / `expect`.

## Deliverables

- A subpath `@sentinelqa/playwright` exported by `packages/ts-runtime` (or split into its own `packages/playwright-helpers` if cleaner — record decision in ADR-0009).
- Exports:
  - `sentinelStep(name: string, fn: () => Promise<void>): Promise<void>` — wraps `test.step`, emits a JSONL `step.start` / `step.end` event with name, durationMs, and any thrown error (stack redacted by the TS-side redactor).
  - `captureEvidence(page: Page, label: string, opts?: { screenshot?: boolean, dom?: boolean, har?: boolean }): Promise<EvidenceRef[]>` — writes screenshots/DOM/HAR snippets into the run dir, returns refs that include in-JSONL `evidence` events.
  - `redactedNetwork(page: Page): Promise<NetworkInterceptor>` — installs a `route` handler that, for every request/response, logs a redacted summary into JSONL (headers + body keys, no secrets).
  - `sentinelTest` — Playwright `test.extend` overlay that auto-installs `redactedNetwork`, configures `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'` (CLAUDE §21).
- A TS-side `redact` mirror of Python's redaction (same rules; tests pin parity).

## Steps

1. Build the helpers with strict types; export only what the public API needs.
2. Implement the TS redactor; sync the rule set with Python's via a shared JSON file under `packages/shared-schema/redaction-rules.json` (single source of truth, generated from Python).
3. Write unit tests with `vitest` mocking Playwright primitives.
4. Document the public API in the package README and link from PRD §15.

## Acceptance criteria

- Authoring a Playwright test using only `sentinelTest` produces JSONL events for every step.
- Redacted network log contains no values matching the shared rules.
- Trace/screenshot/video toggles match CLAUDE §21 defaults.

## Tests required

- `tests/unit/helpers.test.ts` — step wrapping, evidence capture, redaction parity (compare against Python by reading the shared JSON).

## PRD / CLAUDE.md references

- PRD §15.2 Example helper, §20 Evidence.
- CLAUDE.md §21 TS rules, §33 Logging & secrets.

## Definition of Done

- [ ] Helpers exported and documented.
- [ ] Redaction parity verified.
- [ ] Tests pass.
- [ ] `STATUS.md` updated.
