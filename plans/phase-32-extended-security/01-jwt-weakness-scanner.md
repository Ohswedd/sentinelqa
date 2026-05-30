# Task 32.01 — JWT-weakness scanner

## Deliverables

- `modules/security/checks/jwt_weakness.py`. Implements the
  `SecurityCheck` Protocol (Phase 13).
- Walks every `Authorization` header value and every cookie value
  captured during the run (re-uses Phase 04's redacted-network capture).
- For each candidate JWT (`eyJ[A-Za-z0-9_-]{20,}\.…`):
  1. Decode header + payload (no signature verify; we are not
     attacking — only inspecting public structure).
  2. Flag `alg: "none"` (CWE-347 / OWASP-API-2023-08; `severity:
     critical`).
  3. Flag HS256 if the JWT verifies against a small fixed wordlist of
     well-known weak secrets (`secret`, `password`, `changeit`,
     `please-change-me`, `null`, `1234`). Wordlist is hard-coded; the
     scanner does NOT iterate against an external dictionary (no
     brute-force).
  4. Flag missing `exp` (`severity: medium`), missing `iss` /
     `aud` on tokens that look multi-tenant (`severity: low`).
  5. Flag `exp` in the past (`severity: medium` — clock-skew risk).
- Every finding carries:
  - `cwe_id`: `CWE-347` (improper signature) / `CWE-613` (insufficient
    session expiration) as appropriate.
  - `attack_id`: `T1606.001` (Web Cookies forged) where the alg=none
    case applies.
  - Evidence: redacted token prefix (first 8 chars + `…`), location
    (URL + cookie name / header name), recommendation.

## Tests required

- `tests/unit/modules/security/test_jwt_weakness.py` — synthetic JWT
  fixtures cover every branch (none, hs256-weak, hs256-strong,
  missing-exp, expired, missing-iss).
- `tests/integration/modules/security/test_jwt_e2e.py` — driven via the
  HAR fixture from Phase 04; asserts the SARIF output carries the
  CWE-347 reference.

## Definition of Done

- [ ] Scanner ships behind Phase 13 `SecurityCheck` Protocol.
- [ ] Hard-coded weak-secret list never expanded into a dictionary
      attack (`tests/security/test_jwt_no_brute_force.py` greps the
      module for any loop over an external resource).
- [ ] `STATUS.md` updated.
