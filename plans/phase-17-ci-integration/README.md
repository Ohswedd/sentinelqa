# Phase 17 — CI Integration

## Objective

Make SentinelQA easy to drop into any CI/CD pipeline (PRD §21, CLAUDE §39): polished GitHub Action, GitLab CI template, PR comment poster, CI modes (`fast`/`standard`/`full`/`nightly`/`release`), and code-scanning upload.

## PRD / CLAUDE.md references

- PRD §21 CI/CD, §17 Config (CI mode).
- CLAUDE.md §17 Quality gates, §39 CI rules.

## Sub-phases & tasks

1. `01-github-action.md` — polished Action with caching, matrix, code-scanning upload.
2. `02-gitlab-ci.md` — equivalent GitLab template.
3. `03-pr-comment-poster.md` — Action step that upserts the PR comment.
4. `04-ci-modes.md` — `sentinel ci` modes implementation.
5. `05-diff-aware.md` — `--diff origin/main...HEAD` impact mapping.
6. `06-tests.md` — CI smoke runs.
7. `07-playwright-discovery-backend.md` — Playwright-driven discovery backend for CSR SPAs (re-homed from Phase 05 by ADR-0010).

## Definition of Done

- A no-op PR runs SentinelQA in CI on a sample app and posts a PR comment.
- SARIF uploaded to GitHub code scanning.
- CI modes documented and tested.
- Diff-aware mode reduces runtime appropriately on small diffs.

## Phase Gate Review

- [ ] GitHub Action green on the example Next.js app.
- [ ] PR comment posted + updated on subsequent runs.
- [ ] Code-scanning ingests SARIF.
- [ ] GitLab template smoke-tested.
- [ ] ADR-0016 (CI modes) committed.
- [ ] `STATUS.md` updated.
