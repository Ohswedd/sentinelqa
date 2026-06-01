# SentinelQA + Claude Desktop

Drop-in example for wiring the SentinelQA MCP server (our product spec, ADR-0023)
into the Claude Desktop client.

## Installation

```bash
# 1. Install SentinelQA (CLI + MCP server)
pip install sentinelqa-cli sentinelqa-mcp

# 2. Add the snippet from `claude_desktop_config.json` in this directory
# to your Claude Desktop config:
#
# macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
# Windows: %APPDATA%\Claude\claude_desktop_config.json
# Linux: ~/.config/Claude/claude_desktop_config.json
#
# 3. Replace SENTINEL_CONFIG with the absolute path to your project's
# sentinel.config.yaml.
#
# 4. Restart Claude Desktop. The twelve `sentinel.*` tools (plus
# `sentinel.ping`) will appear in the tool picker.
```

## Quick smoke test

From the Claude Desktop tool picker:

1. Call `sentinel.ping` — should return `{status: "ok", server: "sentinelqa-mcp"}`.
2. Call `sentinel.audit` with `url=http://localhost:3000` (or your project's `target.base_url`). The result envelope carries the typed AuditResult plus evidence_refs pointing at the persisted run dir.

## Safety boundary

The MCP server enforces SafetyPolicy on every URL argument before any
SDK call. Targets outside `target.allowed_hosts` (and not local) surface
as agent-envelope errors with `code=UNSAFE_TARGET`, `exit_code=4`. There
is no MCP argument that disables the safety boundary; destructive checks
require the project's `sentinel.config.yaml` to explicitly opt in and
provide a proof-of-authorization file.

## Generic MCP clients

Any MCP-1.0 client speaking the `2024-11-05` protocol version over
stdio can drive the same surface:

```bash
sentinelqa-mcp # stdio (what Claude Desktop uses)
sentinelqa-mcp --http 8765 # loopback HTTP debug loop
sentinel mcp --log-level DEBUG
```
