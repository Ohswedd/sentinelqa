# Task 16.03 — Agent messages

## Deliverables

- Every public exception has `to_agent_message() -> dict` (from Phase 01).
- `Finding.to_agent_message()` returns: `{type:"finding", id, severity, category, title, description, recommendation, evidence_paths, schema_version}`.
- `AuditResult.to_agent_messages()` returns a list combining: run summary message, per-finding messages, blocker summary, suggested next actions.
- `RepairSuggestion.to_agent_message()` returns the proposal in the schema from CLAUDE §23.
- Helper `sentinelqa.agent.format(messages, *, format='ndjson'|'jsonl'|'list') -> str` for piping to an LLM.

## Acceptance criteria

- Every public exception and finding has a stable agent-message shape (golden tests).
- Schema versions match the artifact schemas.

## Tests required

- `tests/golden/sdk/test_agent_messages.py`.

## PRD / CLAUDE.md references

- PRD §14.2, §15.
- CLAUDE.md §15, §32.

## Definition of Done

- [ ] Agent-message format locked and tested.
- [ ] `STATUS.md` updated.
