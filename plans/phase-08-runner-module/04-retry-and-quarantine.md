# Task 08.04 — Retry & quarantine

## Objective

Implement smart retry for flaky tests, and an explicit quarantine list so flaky tests don't silently degrade quality scores.

## Deliverables

- Config keys: `runner.retries.max` (default 1), `runner.retries.backoff_ms` (default 1000), `runner.quarantine.path` (default `tests/sentinel/.quarantine.yaml`).
- Behavior:
  - A test that passes on retry is recorded as `flaky` (counted toward flake rate, not toward `failed`).
  - A test in the quarantine list runs but its result does NOT block the quality gate; it produces an `info` finding instead. Quarantined tests must have an expiry date in the YAML (max 14 days by default) and an issue reference.
  - The flake rate per run is reported; if > `policy.max_flake_rate`, the gate fails.
- A small `engine/runner/quarantine.py` module managing the list (read, validate, expire).

## Steps

1. Wire retry into the JSONL aggregator.
2. Implement the quarantine list with strict schema (test_id, reason, expires_at, issue_url).
3. Wire flake-rate calculation into `ModuleResult.metrics`.

## Acceptance criteria

- A test that fails once then passes is recorded as `flaky`.
- Quarantined test does not block.
- Expired quarantine entry is rejected at load time.

## Tests required

- `tests/unit/runner/test_retry.py`.
- `tests/unit/runner/test_quarantine.py`.

## PRD / CLAUDE.md references

- PRD §9.5 Analyzer, §19 Scoring (flake), §29.2 Flake risks.
- CLAUDE.md §9, §23 Self-healing (no weakening).

## Definition of Done

- [ ] Retry + quarantine implemented and tested.
- [ ] Flake-rate reported.
- [ ] `STATUS.md` updated.
