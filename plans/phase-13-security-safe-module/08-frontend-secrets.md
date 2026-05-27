# Task 13.08 — Frontend secrets / data leakage

## Deliverables

- Scan loaded JS bundles for secrets (using Phase 01 redaction rules in detection mode, not redaction mode).
- Scan DOM, `localStorage`, and `sessionStorage` post-login for tokens/keys.
- Findings:
  - Hardcoded API key in JS bundle → high.
  - JWT or session token written to localStorage → medium-high (with notes about XSS exposure).
  - PII (emails, phone numbers in test) in DOM by anonymous user → variable severity.
- Sensitive-data-in-DOM/network rule from PRD §10.7.

## Acceptance criteria

- Fixture with hardcoded API key in JS → finding.
- Token in localStorage → finding.

## Tests required

- `tests/integration/modules/security/test_frontend_secrets.py`.

## PRD / CLAUDE.md references

- PRD §10.7, §10.9.
- CLAUDE.md §26, §33.

## Definition of Done

- [ ] Scanners implemented.
- [ ] Findings normalized.
- [ ] `STATUS.md` updated.
