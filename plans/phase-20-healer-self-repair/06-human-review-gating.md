# Task 20.06 — Human-review gating

## Deliverables

- Auto-apply policy (`policy.healer.auto_apply`):
  - `off`: nothing applies automatically.
  - `safe`: only locator + wait-condition repairs at confidence ≥ threshold; never assertion changes.
  - `aggressive`: also assertion stabilizations, but only with `--allow-weaken` flag.
- Every applied repair leaves a Conventional-Commit message proposal and an audit-log entry.
- Hand-edited specs: detect via banner absence or via git history (file changed since last `sentinel generate`). Healer never applies to hand-owned files.

## Acceptance criteria

- Default mode never auto-applies assertion changes.
- Hand-edited spec is left alone.

## Tests required

- `tests/unit/healer/test_review_gating.py`.

## PRD / CLAUDE.md references

- PRD §9.6, §6 (safe defaults).
- CLAUDE.md §23.

## Definition of Done

- [ ] Gating logic + tests.
- [ ] `STATUS.md` updated.
