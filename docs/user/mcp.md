# `sentinel mcp` — Model Context Protocol server

Status: `Stable` (, ADR-0023).

`sentinel mcp` starts the SentinelQA MCP server. The server speaks
the [Model Context Protocol](https://spec.modelcontextprotocol.io/)
`2024-11-05` over stdio (the base transport every MCP client uses) and
exposes twelve `sentinel.*` tools that map one-to-one onto
the Phase-16 Python SDK.

## Quick start

```bash
# Default: speak the stdio transport on this process. This is what
# Claude Desktop and other MCP clients invoke.
sentinel mcp

# Local HTTP debug loop on loopback only.
sentinel mcp --http 8765

# Verbose logs to stderr.
sentinel mcp --log-level DEBUG
```

The CLI exit codes follow the canonical grid:

| Code | Meaning                                             |
| ---: | --------------------------------------------------- |
|    0 | Clean exit (peer closed; user interrupted).         |
|    2 | Config error.                                       |
|    4 | Refused unsafe transport (non-loopback HTTP, etc.). |
|    7 | Internal error.                                     |

## Wire protocol

- JSON-RPC 2.0 over NDJSON-framed stdio (one message per line).
- MCP protocol version: `2024-11-05` only. Newer versions are rejected with `-32602` so a future SDK upgrade is a deliberate change.
- Methods implemented: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`. `notifications/cancelled` is observed.

## Tools

Every tool's response is an [agent envelope](../../packages/shared-schema/agent-envelope.schema.json):

```json
{
  "schema_version": "1",
  "tool": "sentinel.audit",
  "result": {
    /* tool-specific payload */
  },
  "errors": [
    /* zero or more error agent-messages */
  ],
  "evidence_refs": [
    /* relative paths under the run directory */
  ]
}
```

| Tool                           | Read-only | What it does                                                          |
| ------------------------------ | --------- | --------------------------------------------------------------------- |
| `sentinel.ping`                | Yes       | Health check. Returns `{status, server, version}`.                    |
| `sentinel.discover`            | Yes       | Crawl `url`; return DiscoveryGraph summary.                           |
| `sentinel.plan`                | Yes       | Build a deterministic TestPlan for `url`.                             |
| `sentinel.generate_tests`      | No        | Render Playwright specs from a plan.                                  |
| `sentinel.run_tests`           | No        | Run the functional suite. Modes: smoke / standard / full.             |
| `sentinel.audit`               | No        | Run the full audit lifecycle.                                         |
| `sentinel.security_audit`      | No        | Safe security checks only.                                            |
| `sentinel.performance_audit`   | No        | Synthetic performance budgets.                                        |
| `sentinel.accessibility_audit` | No        | axe-core + deterministic a11y checks.                                 |
| `sentinel.read_report`         | Yes       | Read a file from a run directory (≤ 256 KiB; binary surfaces as hex). |
| `sentinel.explain_failure`     | Yes       | Return category + recommendation for a finding.                       |
| `sentinel.suggest_fix`         | Yes       | Return the deterministic remediation for a finding.                   |
| `sentinel.verify_fix`          | No        | Re-run the audit and diff findings. Returns a four-valued decision.   |

## Safety contract

Every tool that takes a `url` argument runs `SafetyPolicy.enforce`
_before any SDK call_. Targets outside `target.allowed_hosts` (and not
local) surface as agent-envelope errors with `code=UNSAFE_TARGET` /
`exit_code=4`. There is no CLI flag and no MCP argument that disables
the safety boundary. Destructive checks (stored XSS / SQLi / SAST)
require both `security.mode=authorized_destructive` in the loaded
config and a valid `target.proof_of_authorization` file
(our engineering rules§15).

Logs always go to stderr — stdout is reserved for MCP wire bytes
.

## Claude Desktop

See `examples/mcp-claude-desktop/` for a drop-in `claude_desktop_config.json`
snippet. After updating the config, restart Claude Desktop; the twelve
`sentinel.*` tools appear in the tool picker automatically.

## Generic MCP clients

The CLI is a thin Typer wrapper over the
[`sentinelqa-mcp`](../../packages/mcp-server/) package; you can also
launch the server directly:

```bash
sentinelqa-mcp --help
python -m sentinelqa_mcp --http 8765
```

The HTTP transport accepts `POST /` with `Content-Type: application/json`,
body is a single JSON-RPC request, response is the JSON-RPC response.
The HTTP transport refuses any non-loopback bind by design — it is for
local development, not production agent traffic.
