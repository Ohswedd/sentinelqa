# Task 18.01 — MCP server skeleton

## Deliverables

- `packages/mcp-server/` — Python package using the official MCP server SDK (`mcp` Python package).
- Server starts on stdio by default (`sentinel mcp`); optionally `--http` for local TCP.
- Health check tool `sentinel.ping` returns `{ status: "ok", version }`.
- Logs go to stderr only (CLAUDE §13); stdout reserved for MCP protocol traffic.

## Acceptance criteria

- `sentinel mcp` starts and answers `tools/list`.

## Tests required

- `tests/integration/mcp/test_server_skeleton.py` using the MCP test client.

## PRD / CLAUDE.md references

- PRD §16.
- CLAUDE.md §15.

## Definition of Done

- [ ] Server skeleton up.
- [ ] `STATUS.md` updated.
