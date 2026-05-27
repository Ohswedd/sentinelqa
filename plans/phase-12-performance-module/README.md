# Phase 12 — Performance Module

## Objective

Implement the **Performance** module (PRD §10.5, §27): enforce page-level and API-level budgets, capture LCP/CLS/INP, JS bundle size, CPU blocking, and repeated-navigation stability. Per CLAUDE §27, results are explicitly labeled **synthetic** (not RUM).

## PRD / CLAUDE.md references

- PRD §10.5 Performance.
- CLAUDE.md §9, §27 Performance rules.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `PerformanceModule`.
2. `02-page-budgets.md` — LCP/CLS/INP approximation per route.
3. `03-api-latency.md` — API endpoint latency budgets.
4. `04-bundle-and-cpu.md` — JS bundle size + CPU blocking detection.
5. `05-repeated-nav-stability.md` — Repeated visits to detect memory leaks.
6. `06-perf-cli.md` — `sentinel perf` command.
7. `07-tests.md` — sweep.

## Definition of Done

- All metrics captured per route with budget evaluation.
- Results labeled synthetic.
- Median over N runs by default.

## Phase Gate Review

- [ ] Budgets enforced; deliberate slow fixture triggers a finding.
- [ ] Median calculation verified.
- [ ] Output labels metrics "synthetic".
- [ ] `STATUS.md` updated.
