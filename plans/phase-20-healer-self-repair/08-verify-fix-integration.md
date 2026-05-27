# Task 20.08 — verify_fix integration

## Deliverables

- Wire the healer's proposals into the MCP `sentinel.verify_fix` tool (Phase 18 §04):
  - Agent picks a proposal, applies, calls `verify_fix`, gets structured outcome.
- The healer never auto-mutates app source — only test code.

## Acceptance criteria

- End-to-end: failing fixture → proposal applied → verify_fix returns `fix_verified`.

## Tests required

- `tests/integration/healer/test_verify_fix_loop.py`.

## PRD / CLAUDE.md references

- PRD §12.7, §16.
- CLAUDE.md §15, §23.

## Definition of Done

- [ ] Loop works end-to-end.
- [ ] `STATUS.md` updated.
