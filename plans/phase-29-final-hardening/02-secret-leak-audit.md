# Task 29.02 — Secret-leak audit

## Deliverables

- Run `detect-secrets` / `gitleaks` over a full sample `.sentinel/runs/<id>/` produced by `make demo`.
- Scan: `report.html`, `report.md`, `findings.json`, `score.json`, `run.json`, `audit.log`, `network/*`, `console/*`, `logs/*`, `traces/*`.
- Failure → fix the redactor (Phase 01.05) and retry. No leak shippable.
- Result: `docs/release/secret-leak-audit-<date>.md`.

## Acceptance criteria

- Zero unredacted secrets across all sampled artifacts.

## Definition of Done

- [ ] Clean run + audit doc.
- [ ] `STATUS.md` updated.
