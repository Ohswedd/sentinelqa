# Phase 10 — Functional Module

## Objective

Implement the **Functional** module (PRD §10.1, §31): execute the functional test plan and produce typed `ModuleResult`. This is the first concrete module that plugs into the orchestrator end-to-end through Planner → Generator → Runner → Analyzer → Reporter.

## PRD / CLAUDE.md references

- PRD §10.1 Functional flows.
- CLAUDE.md §9 Module contract, §10 Run lifecycle.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `SentinelModule` impl `FunctionalModule` (CLAUDE §9).
2. `02-flow-coverage.md` — login/signup/logout/password-reset/CRUD/role/admin/file/payment-sandbox/notification-link coverage.
3. `03-flow-tags-and-priority.md` — tag-driven selection (`--grep @p0`).
4. `04-functional-cli.md` — `sentinel functional` command.
5. `05-tests.md` — sweep, with at least one passing + one failing scenario in fixture.

## Definition of Done

- Functional module registered with the orchestrator.
- Plan → spec → run → result loop verified against the fixture app for every PRD §10.1 flow type that the fixture covers.
- Findings (failures) include all evidence required by PRD §20.

## Phase Gate Review

- [ ] Module registered; lifecycle runs it.
- [ ] All §10.1 flow extractors with fixtures pass green.
- [ ] Failing fixture scenario produces full evidence.
- [ ] `STATUS.md` updated.
