# Task 19.08 — Hardcoded demo credentials

## Deliverables

- Scan JS bundles + repo source (when `source.root` is provided) for hardcoded credentials:
  - Strings like `admin@example.com / password123`.
  - Patterns: `username:.*admin.*password:.*`.
  - `.env` values present in JS source (e.g. a database URL accidentally bundled).
- Findings: `LLM-HARDCODED-CRED`, severity high.

## Acceptance criteria

- Fixture with hardcoded admin creds in `app.js` → finding.

## Tests required

- `tests/integration/modules/llm_audit/test_hardcoded_creds.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31, §33.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
