# Task 03.03 — `score.json` schema

## Objective

Define the canonical schema for the quality score so it is fully reproducible from `findings.json` + the config snapshot.

## Deliverables

- `packages/shared-schema/score.schema.json`:
  - `schema_version`, `run_id`, `total` (0–100), `components` (object: `functional`, `security`, `performance`, `accessibility`, `api`, `visual`, `llm_audit`, `flake_risk`), `weights` (mirror of the components), `severity_penalties` (object summarizing penalty applied per severity), `blockers` (array of finding IDs that blocked release), `release_decision` (one of PRD §19.3), `policy` ({ min_quality_score, block_on_critical, block_on_high_security, max_failed_p1_flows, max_flake_rate }).
- `engine/reporter/score_writer.py` — writes `score.json` from a `QualityScore` and `PolicyDecision`.
- Goldens for: passing run, blocked-on-critical, passing-with-warnings, unsafe_blocked (score null), dry_run (score null).
- A reproducibility test: load findings.json + score.json + config snapshot, recompute score, must match exactly.

## Steps

1. Schema author + validation.
2. Writer with deterministic float formatting (round to 2 decimals).
3. Reproducibility test scaffold (Phase 14 implements the actual scoring; this writer just persists the result).

## Acceptance criteria

- Score schema validates goldens.
- Floats serialize with consistent precision (no `0.1 + 0.2` drift).
- `release_decision` enum strictly enforced.

## Tests required

- `tests/golden/reports/test_score_json.py`.
- `tests/unit/reporter/test_score_writer.py`.

## PRD / CLAUDE.md references

- PRD §19 Quality Scoring.
- CLAUDE.md §25 Quality score rules.

## Definition of Done

- [ ] Schema + writer + goldens committed.
- [ ] Deterministic formatting verified.
- [ ] `STATUS.md` updated.
