# Task 13.04 — CORS & CSRF

## Deliverables

- CORS:
  - For each detected API endpoint, send an OPTIONS request from a non-allowlisted origin and inspect `Access-Control-Allow-Origin`.
  - Findings: wildcard ACAO + credentials → critical; reflective ACAO without allowlist → high.
- CSRF:
  - For state-changing endpoints (POST/PUT/PATCH/DELETE) discovered behind auth, check for CSRF tokens or `SameSite` cookies.
  - Heuristic: form-based POSTs missing CSRF token + auth cookie without `SameSite=Strict|Lax` → high.

## Acceptance criteria

- Fixture with wildcard ACAO + credentials triggers critical.
- CSRF-vulnerable fixture endpoint triggers high.

## Tests required

- `tests/integration/modules/security/test_cors.py`.
- `tests/integration/modules/security/test_csrf.py`.

## PRD / CLAUDE.md references

- PRD §10.7.
- CLAUDE.md §26.

## Definition of Done

- [ ] CORS + CSRF checks implemented.
- [ ] `STATUS.md` updated.
