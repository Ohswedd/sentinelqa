# Task 00.09 — Developer docs

## Objective

Give a new contributor (human or agent) the docs they need to clone, install, lint, type-check, test, and ship a first PR without asking anyone for help.

## Prerequisites

- Tasks 00.01–00.08 complete.

## Deliverables

- `CONTRIBUTING.md` (repo root) that covers:
  - How to clone, install (`make install`), and verify (`make ci`).
  - Branching + commit conventions (link to `docs/dev/branching.md` and `docs/dev/commits.md`).
  - How to read `plans/` and pick up the next task from `plans/STATUS.md`.
  - Definition of Done checklist quoted from `CLAUDE.md` §18.
  - How to write/update an ADR.
  - How to update `PRD.md` (and the rule that you must).
- `docs/dev/local-setup.md` listing prerequisites:
  - Python 3.11+ (recommend 3.12).
  - Node.js 20+.
  - `uv` (or `pip-tools`), `pnpm` (or `npm`).
  - Playwright system deps (`npx playwright install --with-deps`).
- `docs/dev/status-labels.md` defining the four documentation status labels from `CLAUDE.md` §34 (`Planned`, `Experimental`, `Stable`, `Deprecated`) and giving worked examples of how to label a feature.
- `docs/dev/agent-workflow.md` describing the `plans/PROMT.md` loop for AI contributors.
- `docs/README.md` listing every doc in the repo with a one-line description.

## Steps

1. Write each doc above. Keep them short, link-heavy, and copy-pasteable.
2. Cross-reference: `CONTRIBUTING.md` must link to `plans/README.md`, `plans/PROMT.md`, `PRD.md`, `CLAUDE.md`, `docs/dev/branching.md`, `docs/dev/commits.md`, `docs/dev/local-setup.md`, `docs/dev/secret-hygiene.md`, `docs/dev/ownership.md`, `docs/adr/README.md`.
3. Add a `markdown-link-check` (or `lychee`) step to CI that fails on broken internal links.

## Acceptance criteria

- A fresh contributor can run `make install` then `make ci` end-to-end using only `CONTRIBUTING.md` and `docs/dev/local-setup.md`.
- `lychee` (or equivalent) reports zero broken internal links.
- Every doc references the relevant PRD/CLAUDE.md sections by number.

## Tests required

- CI link-checker job passes.
- Manual: a teammate (or the user) performs the cold-start onboarding once and confirms it works. Capture any friction back into `CONTRIBUTING.md`.

## PRD / CLAUDE.md references

- PRD §32 Recommended Build Order.
- CLAUDE.md §17 Quality Gates, §18 Definition of Done, §34 Documentation rules.

## Definition of Done

- [ ] All listed docs committed.
- [ ] Link checker green.
- [ ] Cold-start onboarding verified.
- [ ] `STATUS.md` updated; Phase 00 ready for Gate Review.
