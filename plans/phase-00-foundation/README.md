# Phase 00 — Foundation

## Objective

Stand up the repository so every later phase has a stable place to work: monorepo layout matching PRD §11.2, language tooling for Python + TypeScript, baseline CI, ADR framework, secret hygiene, conventional-commit enforcement, and the initial license / `.gitignore` / `.env.example`.

No product behavior exists yet at the end of this phase — only scaffolding. But the scaffolding must be production-quality: deterministic installs, reproducible lint/format/typecheck, CI that runs on every PR.

## PRD / CLAUDE.md references

- PRD §7 Scope, §11.2 Repository structure, §11.3 Language strategy, §32 Recommended Build Order (1).
- CLAUDE.md §3 Privacy/ownership, §4 Git workflow, §7 Architecture, §17 Quality Gates, §20 Python rules, §21 TypeScript rules, §33 Logging & secrets, §39 CI rules, §43 Implementation Order (item 1).

## Sub-phases & tasks

Execute in order:

1. `01-repo-structure.md` — create the monorepo skeleton exactly as PRD §11.2.
2. `02-python-tooling.md` — `pyproject.toml`, `ruff`, `mypy`, `pytest`, `uv`/`pip` lockfile strategy.
3. `03-typescript-tooling.md` — workspaces, `tsconfig`, `eslint`, `prettier`, Playwright install harness.
4. `04-secret-hygiene.md` — `.gitignore`, `.env.example`, redaction utilities scaffold, pre-commit secret scan.
5. `05-conventional-commits.md` — commitlint config + `commit-msg` hook, branch-naming docs.
6. `06-ci-bootstrap.md` — GitHub Actions matrix that runs format/lint/typecheck/tests for every package.
7. `07-adr-framework.md` — `docs/adr/` directory, ADR template, ADR-0001 "Repository structure" recording this phase's decisions.
8. `08-license-and-ownership.md` — LICENSE file, CODEOWNERS, repo metadata; explicitly forbid AI co-owners (`CLAUDE.md` §3).
9. `09-developer-docs.md` — `CONTRIBUTING.md`, `docs/dev/local-setup.md`, status-labeling convention.

## Definition of Done

- `pip install -e packages/python-sdk` and `npm install` both succeed on a clean clone.
- `make lint`, `make typecheck`, `make test` (or equivalent task runner) all pass against an empty codebase.
- CI runs and is green on a no-op PR.
- ADR-0001 exists and references PRD §11.
- `.env.example` exists; no `.env` is in git.
- `git status` clean after the phase commit.

## Phase Gate Review

Before flipping the phase to `[x]` in `STATUS.md`, confirm:

- [ ] Repository tree exactly matches PRD §11.2.
- [ ] Python: `ruff check .`, `ruff format --check .`, `mypy`, `pytest` all green (even if no tests yet, the harness runs).
- [ ] TypeScript: `tsc --noEmit`, `eslint .`, `prettier --check .` all green for every workspace.
- [ ] CI workflow file exists and passed at least one run.
- [ ] `.env.example` lists every variable the PRD references (`TEST_USER_EMAIL`, `TEST_USER_PASSWORD`, plus placeholders for provider keys behind feature flags).
- [ ] `commitlint` enforces Conventional Commits; demo bad commit is rejected by the hook.
- [ ] ADR-0001 (Repository structure) committed.
- [ ] No AI/agent listed as owner, maintainer, or co-author (per `CLAUDE.md` §3).
- [ ] `PRD.md` updated only if Phase 00 deviated from §11.2 — and the deviation is justified inline.
- [ ] `STATUS.md` Phase 00 row signed.
