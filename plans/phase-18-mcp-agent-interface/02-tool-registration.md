# Task 18.02 — Register all 12 PRD §16 tools

## Deliverables

Register the full PRD §16.1 set:

- `sentinel.discover`
- `sentinel.plan`
- `sentinel.generate_tests`
- `sentinel.run_tests`
- `sentinel.audit`
- `sentinel.security_audit`
- `sentinel.performance_audit`
- `sentinel.accessibility_audit`
- `sentinel.read_report`
- `sentinel.explain_failure`
- `sentinel.suggest_fix`
- `sentinel.verify_fix`

For each tool:

- Schema (JSON Schema) for arguments and result.
- Implementation calls into the Python SDK (Phase 16).
- Safety: every tool that takes a URL calls `SafetyPolicy.enforce`.
- Read-only tools are flagged as such for clients that respect read-only hints.
- Long-running tools stream progress as MCP progress notifications.

## Acceptance criteria

- `tools/list` returns all 12; descriptions match PRD §16 example.
- Calling each tool against the fixture returns valid structured output.

## Tests required

- `tests/integration/mcp/test_tools_contract.py` — one test per tool.

## PRD / CLAUDE.md references

- PRD §16.
- CLAUDE.md §15, §6 (safety).

## Definition of Done

- [ ] All tools registered and tested.
- [ ] `STATUS.md` updated.
