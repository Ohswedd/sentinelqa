# Phase 18 — MCP & Agent Interface

## Objective

Build a Model Context Protocol (MCP) server (`packages/mcp-server`) exposing every PRD §16 tool, plus a small Python `agent` helper for non-MCP agent flows. Agent operations must be deterministic, structured, evidence-based, and safe by default (CLAUDE §15).

## PRD / CLAUDE.md references

- PRD §15 Agent rules, §16 MCP tools, §31 open question 5 (yes, day-one MCP).
- CLAUDE.md §15 Agent rules.

## Sub-phases & tasks

1. `01-mcp-server-skeleton.md` — MCP server stand-up.
2. `02-tool-registration.md` — Register all 12 `sentinel.*` tools.
3. `03-agent-message-format.md` — Wire SDK agent messages into responses.
4. `04-verify-fix.md` — `sentinel.verify_fix` end-to-end loop.
5. `05-agent-cli.md` — `sentinel mcp` command starting the server.
6. `06-tests.md` — Contract tests using a real MCP client.

## Definition of Done

- An MCP-capable client (e.g. Claude Desktop) can connect and call every tool.
- All tools return structured results.
- Verify-fix loop demonstrably accepts a `RepairSuggestion` and reruns the affected tests.

## Phase Gate Review

- [ ] MCP server starts and lists tools.
- [ ] Every PRD §16 tool callable with structured args.
- [ ] Verify-fix loop completes against fixture.
- [ ] ADR-0017 (Agent / MCP boundary) committed.
- [ ] `STATUS.md` updated.
