# Phase 09 — Analyzer Module

## Objective

Implement the **Analyzer** (PRD §9.5): interpret failures from `ModuleResult`s, produce a root-cause hypothesis with confidence, attach reproduction steps, and decide whether each failure should retry or quarantine.

## PRD / CLAUDE.md references

- PRD §9.5 Analyzer.
- CLAUDE.md §9 Module contract, §23 Self-healing, §24 Findings.

## Sub-phases & tasks

1. `01-failure-categorization.md` — app bug vs test bug vs env vs flake.
2. `02-root-cause-hypothesis.md` — deterministic rules with confidence.
3. `03-repro-steps.md` — reproducible step list per failure.
4. `04-retry-quarantine-decision.md` — when to retry vs flag.
5. `05-llm-explainer-adapter.md` — optional LLM explainer behind interface.
6. `06-analyzer-tests.md` — sweep.

## Definition of Done

- Every failure gets a category + confidence + reproduction.
- Deterministic core; LLM optional.
- Output feeds the Reporter, Healer, and SDK agent messages.

## Phase Gate Review

- [ ] Categorization correct on fixture failures (app vs test vs env).
- [ ] Repro steps verified manually for a sample failure.
- [ ] LLM adapter optional and budget-bounded.
- [ ] ADR-0013 (Analyzer rules) committed.
- [ ] `STATUS.md` updated.
