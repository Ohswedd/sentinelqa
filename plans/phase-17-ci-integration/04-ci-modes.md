# Task 17.04 — `sentinel ci` modes

## Deliverables

- Replace Phase 02 stub of `ci`.
- Modes (PRD §21.3):
  - `fast`: smoke (P0) + impacted tests (from diff).
  - `standard`: impacted + required gates (functional + security + a11y at default tags).
  - `full`: full regression.
  - `nightly`: full + chaos + extended security.
  - `release`: full + strict policy (raises `policy.min_quality_score` floor unless overridden).
- Each mode is a preset over `--modules` + `--grep` + policy overrides; the underlying lifecycle is unchanged.
- Mode contract codified in `engine/ci/modes.py`.

## Acceptance criteria

- Each mode produces a different set of executed modules + tests.
- Mode selection visible in `run.json`.

## Tests required

- `tests/unit/ci/test_modes.py`.
- `tests/integration/cli/test_ci_modes.py`.

## PRD / CLAUDE.md references

- PRD §21.3.
- CLAUDE.md §39.

## Definition of Done

- [ ] Modes implemented + tested.
- [ ] `STATUS.md` updated.
