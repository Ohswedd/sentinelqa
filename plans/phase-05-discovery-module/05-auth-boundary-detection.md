# Task 05.05 — Auth boundary detection

## Objective

Detect which routes require authentication, which roles, and how the app behaves at the auth boundary.

## Deliverables

- `engine/discovery/auth_boundary.py` producing `AuthBoundary` records:
  - route, requires_auth (bool), redirects_to (login URL if unauthenticated visit redirects), roles_required (best-effort), evidence (response status, redirect chain, cookies set, UI markers like "Sign in").
- Two crawl passes when auth config is present:
  - Anonymous pass — establishes which routes redirect or 401/403.
  - Authenticated pass (using `auth.login_url` + `*_env` credentials) — establishes which routes are reachable as a logged-in user.
- Comparison produces the boundary map.
- Detects:
  - UI-only auth: the frontend hides a route but the backend serves it to anonymous requests. (Critical signal for Phase 19 LLM audit.)
  - Role escalation hints: a route that returns 200 to a low-privilege user when the UI implies it should be admin-only.

## Steps

1. Build the anonymous crawl pass (reuse 05.01).
2. Build the authenticated pass: log in via Playwright using `auth.login_url` + env credentials; persist session/cookies for subsequent requests.
3. Run both passes; diff and produce `auth.json`.
4. Add safety: never store the real password in artifacts; only references to env var names.

## Acceptance criteria

- Fixture app with `/login` + `/dashboard` correctly identifies `/dashboard` as auth-required.
- A misconfigured fixture (route hidden in UI but reachable anonymously) produces a UI-only-auth flag.

## Tests required

- `tests/integration/discovery/test_auth_boundary.py`.

## PRD / CLAUDE.md references

- PRD §9.1, §10.7 Auth boundary, §10.9 LLM audits.
- CLAUDE.md §6, §9, §31.

## Definition of Done

- [ ] Boundary detection works for fixture.
- [ ] No real passwords in artifacts.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
