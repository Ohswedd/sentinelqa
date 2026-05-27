# Phase 14 — Quality Scoring

## Objective

Implement the reproducible **Quality Score** (PRD §19, CLAUDE §25): derive a 0–100 score from findings + module results + config weights + flake risk; produce a typed `PolicyDecision` with release decision and blockers.

Score must be **explainable** and **reproducible**: same inputs → same score.

## PRD / CLAUDE.md references

- PRD §19 Quality Scoring.
- CLAUDE.md §25 Quality score rules.

## Sub-phases & tasks

1. `01-score-model.md` — Components, weights, severity penalties.
2. `02-blockers.md` — Critical findings, security-high, p1 flow failures.
3. `03-release-decision.md` — `pass`, `pass_with_warnings`, `blocked`, `inconclusive`, `unsafe_target_rejected`.
4. `04-policy-gate.md` — Apply `policy.*` from config; return `PolicyDecision`.
5. `05-reproducibility.md` — Property tests asserting determinism.
6. `06-cli-and-explain.md` — `sentinel report --explain-score` shows the math.
7. `07-tests.md` — sweep.

## Definition of Done

- Score reproducible from inputs; tests prove it.
- Release decision tracks PRD §19.3.
- Score artifact validates against `score.schema.json` (Phase 03).

## Phase Gate Review

- [ ] Score model audited; weights default to PRD §19.1.
- [ ] Blockers identified correctly.
- [ ] Property tests for reproducibility green.
- [ ] `STATUS.md` updated.
