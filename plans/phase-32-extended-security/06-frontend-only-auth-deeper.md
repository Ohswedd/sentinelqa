# Task 32.06 — Frontend-only auth detector (deeper)

## Deliverables

- Phase 19's existing "frontend-only auth" check gains a deeper probe:
  1. Run Playwright against the protected route as identity **A**.
  2. Record every XHR / fetch / subresource URL the page issues
     (re-uses Phase 04's network capture).
  3. For each unique server endpoint, issue an anonymous `httpx`
     request from outside the browser context. Expect 401 / 403.
  4. If any endpoint returns 200 with body payload, finding:
     `frontend-only-auth` (CWE-862 / OWASP-API-2023-01; `severity:
     high`).
- The check distinguishes between:
  - Truly anonymous endpoints (intentional; e.g. `/api/public/...`)
    — recognised via Phase 19's `apparently_public` heuristic and
    excluded.
  - Endpoints that 401/403 anonymously but return data with A's
    cookies — pass.
  - Endpoints that return data anonymously — the failure case.

## Tests required

- `tests/unit/modules/llm_audit/test_frontend_only_auth_deeper.py` —
  classification logic (apparently-public vs gated vs broken).
- `tests/integration/modules/llm_audit/test_frontend_only_auth_e2e.py`
  — driven against a stub server that has two endpoints (one
  gated correctly, one not).

## Definition of Done

- [ ] Deeper probe ships behind Phase 19's existing module.
- [ ] False-positive rate on Phase 26 examples = 0.
- [ ] `STATUS.md` updated.
