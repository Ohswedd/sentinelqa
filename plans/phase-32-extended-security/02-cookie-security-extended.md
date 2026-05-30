# Task 32.02 — Cookie security audit (extended)

## Deliverables

- Extend `modules/security/checks/cookies.py` (Phase 13) with four new
  rules:
  1. Missing `__Host-` / `__Secure-` prefix on session-shaped cookies
     (CWE-1004; `severity: medium`).
  2. Missing `SameSite` attribute on cross-site-likely cookies
     (CWE-1275; `severity: medium`).
  3. Over-broad `Domain` attribute (e.g. cookie set on `app.foo.com`
     scoped to `.foo.com`) — `severity: medium`.
  4. Over-broad `Path` attribute (`Path=/` on a sensitive cookie)
     — `severity: low`, context-dependent.
- All four findings carry `cwe_id`, ATT&CK `T1606.001` where applicable,
  recommendation, and a Set-Cookie evidence row redacted via Phase 01's
  redactor.
- Updates `tests/integration/modules/security/test_cookie_audit.py`
  with fixtures for every new rule.

## Tests required

- Unit tests for each rule's parser (good / bad / edge cases).
- Integration test confirms the SARIF output references CWE-1004 +
  CWE-1275.

## Definition of Done

- [ ] Four new rules ship, every existing Phase-13 test still green.
- [ ] CWE references in findings.
- [ ] `STATUS.md` updated.
