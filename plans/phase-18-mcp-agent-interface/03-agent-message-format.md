# Task 18.03 — Agent message format

## Deliverables

- Tool results use the `to_agent_message()` shapes from Phase 16 task 16.03.
- A consistent envelope: `{ schema_version, tool, result, errors, evidence_refs }`.
- Errors mapped to `agent_message` form with `code`, `message`, `suggested_fix`.

## Acceptance criteria

- Every tool's success and failure paths produce schema-valid envelopes.

## Tests required

- `tests/golden/mcp/test_tool_envelopes.py`.

## PRD / CLAUDE.md references

- PRD §15, §16.3.
- CLAUDE.md §15, §32.

## Definition of Done

- [ ] Envelope locked.
- [ ] `STATUS.md` updated.
