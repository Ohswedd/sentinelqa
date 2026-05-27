# Task 21.06 — CI never auto-accepts baselines

## Deliverables

- The CLI flag `--accept-baselines` is permitted **only** when `SENTINEL_CI != true` AND the user passes it interactively (or with explicit `--non-interactive`).
- In CI mode, attempting to accept baselines fails fast (exit 4 — unsafe).
- Audit log records every baseline acceptance.

## Acceptance criteria

- `CI=true sentinel visual --accept-baselines` exits non-zero with a refusal.
- Local interactive accept works.

## Tests required

- `tests/integration/modules/visual/test_no_auto_accept.py`.

## PRD / CLAUDE.md references

- PRD §10.6.
- CLAUDE.md §29, §39.

## Definition of Done

- [ ] CI guard verified.
- [ ] `STATUS.md` updated.
