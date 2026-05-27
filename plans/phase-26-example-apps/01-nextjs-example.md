# Task 26.01 — Next.js example

## Deliverables

- `examples/nextjs/` containing a small but realistic Next.js 14 app:
  - Routes: `/`, `/login`, `/signup`, `/dashboard`, `/projects`, `/projects/[id]`, `/admin`.
  - Auth via NextAuth (or a simple cookie-based stub).
  - CRUD for "Project" entity via in-memory or SQLite.
  - Decent accessibility, headers, etc.
- `examples/nextjs/sentinel.config.yaml` pre-configured.
- `examples/nextjs/README.md` showing `make demo:nextjs` -> `sentinel audit`.

## Acceptance criteria

- `make demo:nextjs` boots the app on port 3000.
- `sentinel audit --url http://localhost:3000` against it produces a score ≥ 85 with no critical findings.

## Tests required

- `tests/integration/examples/test_nextjs.py`.

## Definition of Done

- [ ] App + config + README.
- [ ] Smoke audit green.
- [ ] `STATUS.md` updated.
