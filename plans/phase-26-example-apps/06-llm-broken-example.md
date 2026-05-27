# Task 26.06 — Deliberately broken AI-generated example

## Deliverables

- `examples/llm-broken/` — a Next.js app that intentionally exhibits every issue from PRD §10.9 / Phase 19:
  - Dead "Save" button.
  - Fake `/api/orders` endpoint missing on server.
  - Mock data shipped in production build.
  - `/admin` hidden in UI but reachable via API.
  - Hardcoded admin creds in `app.js`.
  - JWT in localStorage.
  - Missing loading/error states.
  - Frontend-only validation.
  - "Coming soon" inside checkout.
  - Console errors silently swallowed.
- `make demo:llm-broken` boots it.
- Used as a marketing/demo reference and as Phase 19's integration target.

## Tests required

- `tests/integration/examples/test_llm_broken_findings.py` — must produce ≥ 8 distinct LLM-audit findings.

## Definition of Done

- [ ] App + tests.
- [ ] `STATUS.md` updated.
