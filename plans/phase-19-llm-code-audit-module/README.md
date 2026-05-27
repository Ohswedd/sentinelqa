# Phase 19 — LLM-Code Audit Module

## Objective

Implement SentinelQA's strongest differentiator (PRD §10.9, §28, §31): an audit module that hunts for AI-generated "fake completeness" — dead buttons, fake routes, mock data shipped, UI-only auth, missing CRUD edges, frontend/backend validation mismatch, hardcoded credentials, localStorage secrets, console errors ignored, "coming soon" placeholders.

This module ties together discovery, generator, runner, and security signals; it does not generate Playwright tests directly — it inspects the app + the discovery graph.

## PRD / CLAUDE.md references

- PRD §10.9 LLM-code audits, §28 Differentiation.
- CLAUDE.md §9, §31 LLM-Code Audit Rules.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `LlmAuditModule`.
2. `02-dead-buttons.md` — Buttons with no handlers.
3. `03-fake-routes.md` — Generated links to nonexistent routes / fake API endpoints.
4. `04-mock-data-shipped.md` — Mock fixtures shipped in production builds.
5. `05-forms-without-submit.md` — Form submission paths broken.
6. `06-missing-crud-edges.md` — Create works; edit/delete missing.
7. `07-frontend-only-auth.md` — UI hides routes the backend serves.
8. `08-hardcoded-creds.md` — Hardcoded demo credentials in code.
9. `09-localstorage-secrets.md` — Tokens in localStorage / sessionStorage.
10. `10-missing-loading-error-states.md` — Loading/error UI gaps.
11. `11-validation-mismatch.md` — Frontend validates, backend doesn't (or vice versa).
12. `12-coming-soon-placeholders.md` — Placeholder leaks in flows.
13. `13-console-errors.md` — Console errors UI ignores.
14. `14-cli-and-report.md` — `sentinel llm-audit` command.
15. `15-tests.md` — sweep with broken fixture variants for each check.

## Definition of Done

- Every PRD §10.9 check implemented, evidence-backed, with `Finding`s using CLAUDE §24 standard.
- Module differentiates SentinelQA in the report (clearly labeled section "LLM-Code Audit").

## Phase Gate Review

- [ ] Every check has at least one fixture that triggers it and one that doesn't.
- [ ] Findings include redacted evidence (screenshot, snippet, network sample).
- [ ] ADR-0018 (LLM-code audit heuristics) committed.
- [ ] `STATUS.md` updated.
