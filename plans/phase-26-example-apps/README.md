# Phase 26 — Example Apps

## Objective

Build the example apps under `examples/` (PRD §11.2) so newcomers can audit a known-good system in one command, and so our integration tests have a realistic surface. Each example is small, deterministic, and self-contained.

## PRD / CLAUDE.md references

- PRD §11.2, §32, §28 (differentiation: real working demos).
- CLAUDE.md §34 docs.

## Sub-phases & tasks

1. `01-nextjs-example.md` — Next.js sample with auth + CRUD.
2. `02-fastapi-example.md` — FastAPI backend with OpenAPI.
3. `03-django-example.md` — Django app + admin.
4. `04-flask-example.md` — Tiny Flask app.
5. `05-react-vite-example.md` — Vite + React frontend.
6. `06-llm-broken-example.md` — Deliberately broken AI-generated app (powers Phase 19 demos).
7. `07-end-to-end-demo.md` — Combined demo: full audit of Next.js + FastAPI yielding HTML report.

## Definition of Done

- Each example runs with `make demo:<name>` in a fresh checkout.
- `sentinel audit --url <example>` produces useful findings on the broken one and clean output on the good ones.

## Phase Gate Review

- [ ] Each example builds + runs.
- [ ] `sentinel audit` smoke against each is documented and reproducible.
- [ ] `STATUS.md` updated.
