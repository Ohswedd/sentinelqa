# Task 32.05 — OWASP API Top-10 BOLA / BFLA via authorized identity replay

## Deliverables

- `modules/security/checks/api_bola_bfla.py`. Requires Phase 13's
  `auth.second_user` config block (already exists) AND
  `security.mode: authorized_destructive` AND a non-empty
  `target.proof_of_authorization` string. Refuses to run otherwise.
- Replay strategy:
  1. The discovery module captures observed API calls as identity
     **A** (the primary `auth` block). Each captured call has a
     redacted URL, method, headers, body shape.
  2. The probe re-issues each captured call under identity **B**
     (the `auth.second_user` block). Two outcomes:
     - 200 with payload referencing A's data → **BOLA**
       (OWASP-API-2023-01; `severity: critical`).
     - 200 for an admin-shaped endpoint when B is not admin →
       **BFLA** (OWASP-API-2023-03; `severity: high`).
  3. Probe is bounded by `target.rate_limit_rps` AND a hard cap of
     50 distinct endpoints per run (`max_endpoints` config; default 50).
- Findings carry `owasp_api_id`, `cwe_id` (CWE-639 BOLA / CWE-863
  BFLA), evidence (redacted request + response), recommendation.

## Tests required

- `tests/unit/modules/security/test_bola_bfla_classifier.py`.
- `tests/integration/modules/security/test_bola_against_stub.py` —
  `pytest-httpserver` stub with two seeded identities.
- `tests/security/test_bola_requires_authorization.py` — refuses to
  run without the destructive-mode + proof-of-authorization combo.

## Definition of Done

- [ ] Probe behind the destructive-mode + PoA gate.
- [ ] Hard cap on endpoint count enforced.
- [ ] Findings include OWASP-API ids.
- [ ] `STATUS.md` updated.
