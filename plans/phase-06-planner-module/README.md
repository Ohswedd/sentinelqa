# Phase 06 — Planner Module

## Objective

Implement the **Planner** (PRD §9.2): consume the `DiscoveryGraph` + `RiskMap` and emit a typed `TestPlan` that prioritizes flows, assigns risk, and enumerates the test types each flow needs. Deterministic core, with an optional LLM adapter behind a strict interface (per PRD §6.8 / open question 6).

## PRD / CLAUDE.md references

- PRD §9.2 Planner, §6 Principles (deterministic where possible), §19 Quality scoring (inputs).
- CLAUDE.md §6, §7, §9, §15 Agent interface (planner is one of the agent operations), §22 Generated test rules.

## Sub-phases & tasks

1. `01-deterministic-core.md` — flows from routes/forms/auth boundaries; priority + risk assignment.
2. `02-flow-extraction.md` — login/signup/CRUD/role/admin/payment/file flows.
3. `03-plan-schema.md` — `plan.json` schema, golden tests.
4. `04-llm-adapter.md` — optional LLM planning behind an interface; provider-agnostic.
5. `05-plan-cli.md` — `sentinel plan` command.
6. `06-planner-tests.md` — unit + integration sweep.

## Definition of Done

- A plan is producible from any `DiscoveryGraph` with no LLM available.
- Plan includes priority (P0–P3), risk (critical/high/medium/low), confidence, test type, required auth role, required data state for every flow.
- LLM adapter is **optional** and behind a feature flag.
- `plan.json` is schema-versioned and round-trippable.

## Phase Gate Review

- [ ] Deterministic plan for the fixture app committed as a golden.
- [ ] LLM adapter behind a configurable interface; absence of LLM credentials doesn't break planning.
- [ ] `sentinel plan` works end-to-end.
- [ ] ADR-0010 (Planner: deterministic vs LLM) committed.
- [ ] `STATUS.md` updated.
