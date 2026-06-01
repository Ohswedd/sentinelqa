# sentinelqa-mcp

The SentinelQA MCP server (our product spec, ADR-0023). Pure-Python, stdlib-only
wire layer over the [Phase-16 Python SDK](../python-sdk/README.md). No
runtime dependencies beyond `sentinelqa`, `sentinelqa-engine`, and
Pydantic 2.10.x.

## Wire protocol

- JSON-RPC 2.0 over NDJSON-framed stdio (the MCP base transport).
- MCP protocol version `2024-11-05` only — newer versions are rejected during `initialize`, not silently accepted.
- Methods: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`. `notifications/cancelled` is observed.

## Tools

The twelve our product spec tools, each implemented in
[`src/sentinelqa_mcp/tools/`](src/sentinelqa_mcp/tools/):

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

Plus a `sentinel.ping` health check.

Every tool result is wrapped in the agent envelope defined in
[`envelope.py`](src/sentinelqa_mcp/envelope.py) (schema
`packages/shared-schema/agent-envelope.schema.json`).

## Running

```bash
# Default: stdio (what Claude Desktop expects).
sentinelqa-mcp

# Local HTTP debug loop (loopback only, refuses public binds).
sentinelqa-mcp --http 8765

# Via the CLI (replaces the stub):
sentinel mcp
sentinel mcp --http 8765 --log-level debug
```

A Claude Desktop config snippet lives at
[`examples/mcp-claude-desktop/claude_desktop_config.json`](../../examples/mcp-claude-desktop/claude_desktop_config.json).

## Safety boundary

Every tool that takes a `url` argument runs `SafetyPolicy.enforce`
before any SDK call. Unsafe targets surface as an envelope with
`result=null` and a single `UNSAFE_TARGET` error agent-message
.
