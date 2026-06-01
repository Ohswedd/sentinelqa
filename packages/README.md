# packages/

Reusable libraries published from this monorepo. the documentation.

- `python-sdk/` — the public Python SDK (`Sentinel`, `AuditResult`, etc.; our product spec,).
- `ts-runtime/` — TypeScript helpers used by Playwright execution.
- `mcp-server/` — MCP server exposing `sentinel.*` tools to LLM coding agents.
- `shared-schema/` — JSON Schema sources for `findings.json`, `score.json`, `run.json`, etc. (our product spec, §20;).

Per our engineering rules and §20, public APIs must be typed and stable. Internal helpers stay out of package root imports.
