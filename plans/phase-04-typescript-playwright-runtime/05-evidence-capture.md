# Task 04.05 — Evidence capture

## Objective

Always-on evidence capture for failing tests; opt-in capture for passing tests. Evidence types: Playwright trace zip, screenshot, video, HAR, console log, network log, DOM snapshot (PRD §20).

## Deliverables

- `sentinelTest` default settings:
  - `trace: 'on-first-retry'` (and `'retain-on-failure'` for already-failed without retry).
  - `screenshot: 'only-on-failure'`.
  - `video: 'retain-on-failure'`.
- A `captureEvidence(page, label)` helper that always writes a screenshot + DOM snapshot, regardless of pass/fail.
- HAR capture toggled via Playwright `recordHar`; opt-in via config (`evidence.har: true`).
- A network log writer that intercepts every request/response with `redactedNetwork` and writes JSONL to `<run-dir>/network/<test-id>.jsonl`.
- A console log writer for browser console messages (`page.on('console')`) into `<run-dir>/console/<test-id>.jsonl`.
- A DOM snapshot helper that captures full HTML + a hash of computed accessibility tree for replay.

## Steps

1. Wire defaults in `sentinelTest`.
2. Implement helpers.
3. Add per-evidence cleanup paths to retention.
4. Verify on the fixture project with a deliberately failing spec.

## Acceptance criteria

- Failing tests always produce trace + screenshot + video + DOM + console + network artifacts.
- Passing tests produce only the JSONL stream unless `captureEvidence` is called.
- All artifacts redacted before write.

## Tests required

- `tests/integration/evidence.test.ts`.
- `tests/integration/evidence/test_python_parses_artifacts.py` — Python parser validates the JSONL outputs.

## PRD / CLAUDE.md references

- PRD §20 Evidence and Reporting.
- CLAUDE.md §21 TS rules.

## Definition of Done

- [ ] Defaults align with CLAUDE §21.
- [ ] Failure evidence always present.
- [ ] Redaction verified.
- [ ] `STATUS.md` updated.
