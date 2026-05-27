# Phase 23 — Chaos Module

## Objective

Implement safe chaos/adversarial testing (PRD §10.8): slow network, offline, API 500 mocking, timeouts, expired sessions, missing permissions, duplicate submissions, double-click races, back/forward navigation, refresh mid-flow, large payloads, empty datasets, browser-storage corruption. All injected via Playwright network/route APIs — no destructive testing against production.

## PRD / CLAUDE.md references

- PRD §10.8 Chaos.
- CLAUDE.md §6, §9.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `ChaosModule`.
2. `02-network-scenarios.md` — Slow / offline / 500 / timeout via Playwright `route`.
3. `03-session-scenarios.md` — Expired token / missing permissions.
4. `04-ux-edge-cases.md` — Duplicate submit / double-click / back-forward / refresh mid-flow.
5. `05-data-scenarios.md` — Empty dataset / large payload / storage corruption.
6. `06-chaos-cli.md` — `sentinel chaos` command.
7. `07-tests.md` — sweep.

## Definition of Done

- Each scenario injectable per route/flow.
- Findings tied to user-visible failure (no graceful handling).
- Defaults off in fast CI; on in nightly.

## Phase Gate Review

- [ ] All scenarios implemented and tested.
- [ ] No destructive defaults.
- [ ] `STATUS.md` updated.
