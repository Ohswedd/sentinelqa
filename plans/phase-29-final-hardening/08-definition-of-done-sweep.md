# Task 29.08 — Definition-of-Done sweep

## Deliverables

- Walk the CLAUDE §18 Definition of Done across the entire repo:
  - Implementation matches PRD (Phase 29.06 confirms).
  - Tests exist and pass (`make ci` green).
  - Types/lint pass.
  - Safety reviewed (Phase 29.01).
  - Reports/schemas updated.
  - Docs/PRD updated.
  - No secrets introduced.
  - `git status` clean.
- A `make dod` command runs the local checks and prints a green/red verdict.

## Acceptance criteria

- `make dod` green.

## Definition of Done

- [ ] DoD check committed and passing.
- [ ] `STATUS.md` updated.
