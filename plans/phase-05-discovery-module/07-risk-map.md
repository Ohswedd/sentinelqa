# Task 05.07 — Risk map

## Objective

Derive a per-route / per-element risk score from the discovery graph so the Planner can prioritize.

## Deliverables

- `engine/discovery/risk_map.py` producing `RiskMap`:
  - Per route: risk score 0–1 with justifications (auth boundary, payment hint, admin path, console error, 5xx endpoint, missing accessible labels).
  - Per element: risk score 0–1.
- Risk model is deterministic and explainable:
  - Login/auth/payment/admin paths → high base risk.
  - Routes triggering 5xx during discovery → very high risk.
  - Routes referencing forms without submit handlers → high risk (likely fake completeness from LLM-generated code).
  - Repeated components → distribute risk across instances.
- The model lives in `engine/discovery/risk_model.py` as a small, audited set of weighted rules. No ML in MVP.

## Steps

1. Define the rule set with weights (numeric, summed and clipped to 0–1).
2. Produce justifications for every score (list of rule names that contributed).
3. Persist `risk.json`.

## Acceptance criteria

- Risk scores reproducible from the same discovery graph (no randomness).
- Justifications listed.

## Tests required

- `tests/unit/discovery/test_risk_model.py` — exhaustive rule coverage.

## PRD / CLAUDE.md references

- PRD §9.1, §19 Scoring.
- CLAUDE.md §9, §19, §25.

## Definition of Done

- [ ] Risk map deterministic and explainable.
- [ ] Tests cover every rule.
- [ ] `STATUS.md` updated.
