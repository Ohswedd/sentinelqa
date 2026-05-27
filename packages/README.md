# packages/

Reusable libraries published from this monorepo. PRD §11.2.

- `python-sdk/` — the public Python SDK (`Sentinel`, `AuditResult`, etc.; PRD §14, Phase 16).
- `ts-runtime/` — TypeScript helpers used by Playwright execution (PRD §15, Phase 04).
- `mcp-server/` — MCP server exposing `sentinel.*` tools to LLM coding agents (PRD §16, Phase 18).
- `shared-schema/` — JSON Schema sources for `findings.json`, `score.json`, `run.json`, etc. (PRD §18, §20; Phase 03).

Per `CLAUDE.md` §14 and §20, public APIs must be typed and stable. Internal helpers stay out of package root imports.
