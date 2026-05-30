# Task 31.08 — Test sweep + docs

## Deliverables

- Per-task unit + integration tests listed in tasks 31.01–31.07 must
  be green together.
- New CI lane `auth-headless` runs the unit + integration tests (gated
  Chromium tests stay behind `SENTINELQA_HAS_CHROMIUM=1`).
- `docs/user/auth-flows.md` written for the three top use cases:
  1. "I want to audit an SSO-protected app" — one-time login flow.
  2. "I want to audit a workflow in my own ChatGPT / Claude / Gemini
     account" — LLM-web-profile flow.
  3. "I want to share a vault entry with a teammate" — `auth export`
     + secure-transport guidance.
- `docs/dev/auth-internals.md` for contributors — vault layout, crypto
  scheme, file permissions, audit-log contract.

## Definition of Done

- [ ] All Phase 31 tests green under `make ci`.
- [ ] Two user-facing doc pages shipped.
- [ ] `STATUS.md` updated.
