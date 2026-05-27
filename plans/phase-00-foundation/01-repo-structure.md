# Task 00.01 — Repository structure & monorepo layout

## Objective

Create the exact directory tree specified in PRD §11.2. Every later phase will create files inside these folders.

## Prerequisites

- Git repo initialized at `/Users/ohswedd/Desktop/SENTINEL QA/` (already done).
- `PRD.md` and `CLAUDE.md` present at repo root.

## Deliverables

The following directories exist at the repo root:

```
apps/
  cli/
  docs/
  dashboard/
packages/
  python-sdk/
  ts-runtime/
  mcp-server/
  shared-schema/
engine/
  orchestrator/
  discovery/
  planner/
  generator/
  runner/
  analyzer/
  healer/
  reporter/
  policy/
modules/
  functional/
  api/
  accessibility/
  performance/
  visual/
  security/
  chaos/
  llm_audit/
integrations/
  github/
  gitlab/
  browserstack/
  saucelabs/
  slack/
  jira/
  linear/
examples/
  nextjs/
  fastapi/
  django/
  flask/
  react-vite/
tests/
  unit/
  integration/
  e2e/
docs/
  adr/
  dev/
  user/
.github/
  workflows/
  ISSUE_TEMPLATE/
```

Each directory must contain a `.gitkeep` (or a `README.md` if helpful) so it is tracked even before code lives in it.

## Steps

1. From repo root, create the tree above with a single scripted `mkdir -p` invocation. Verify the tree with `tree -L 3 -I node_modules` (or `find . -maxdepth 3 -type d`).
2. Add a one-paragraph `README.md` to every top-level folder (`apps/`, `packages/`, `engine/`, `modules/`, `integrations/`, `examples/`, `docs/`) describing what lives there, citing the relevant PRD section. Keep it short.
3. Create the top-level repo `README.md` that introduces SentinelQA, links to `PRD.md`, `CLAUDE.md`, and `plans/README.md`, and lists the supported languages (Python + TypeScript).
4. Commit on a fresh branch `feature/phase-00-repo-structure`.

## Acceptance criteria

- Every folder in PRD §11.2 exists with at least a placeholder file.
- Each top-level folder has a `README.md` that cites a PRD section.
- Repo `README.md` includes the safety-boundary one-liner from `CLAUDE.md` §6 ("authorized testing only — no stealth, no evasion").
- No source code yet — scaffolding only.

## Tests required

None for this task (no code yet). The verification is the directory listing.

## PRD / CLAUDE.md references

- PRD §11.2 Repository structure.
- CLAUDE.md §7 Architecture, §43 Implementation Order (item 1).

## Definition of Done

- [ ] Directory tree matches PRD §11.2 exactly.
- [ ] Each top-level folder has an explanatory `README.md`.
- [ ] Repo `README.md` exists with PRD/CLAUDE.md links and safety one-liner.
- [ ] Conventional-commit landed (e.g. `chore(repo): scaffold monorepo per PRD §11.2`).
- [ ] `STATUS.md` updated: task 00.01 marked done; pointer advanced to 00.02.
