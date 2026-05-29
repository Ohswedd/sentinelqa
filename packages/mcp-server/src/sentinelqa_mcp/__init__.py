"""sentinelqa-mcp — the SentinelQA MCP server (PRD §16, ADR-0023).

Public surface:

- :class:`MCPServer` — the dispatcher; constructible without a transport.
- :func:`build_default_server` — convenience factory that wires the
  default :class:`SentinelToolset` against a :class:`sentinelqa.Sentinel`.
- :data:`AGENT_ENVELOPE_SCHEMA_VERSION` — the envelope schema version.
- :data:`MCP_PROTOCOL_VERSION` — the MCP protocol version we speak.
- :data:`SERVER_NAME` / :data:`SERVER_VERSION` — used in the
  ``initialize`` handshake.

Heavy imports (the transports, tool modules) are imported lazily by the
factory so ``import sentinelqa_mcp`` stays fast for the CLI ``--help``
path.
"""

from __future__ import annotations

from sentinelqa_mcp.envelope import AGENT_ENVELOPE_SCHEMA_VERSION, AgentEnvelope
from sentinelqa_mcp.errors import (
    JSONRPC_APPLICATION_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INVALID_REQUEST,
    JSONRPC_METHOD_NOT_FOUND,
    JSONRPC_PARSE_ERROR,
    ToolError,
)
from sentinelqa_mcp.protocol import (
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    ToolSpec,
)
from sentinelqa_mcp.server import MCPServer, build_default_server

__all__ = [
    "AGENT_ENVELOPE_SCHEMA_VERSION",
    "AgentEnvelope",
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPC_APPLICATION_ERROR",
    "JSONRPC_INVALID_PARAMS",
    "JSONRPC_INVALID_REQUEST",
    "JSONRPC_METHOD_NOT_FOUND",
    "JSONRPC_PARSE_ERROR",
    "MCPServer",
    "MCP_PROTOCOL_VERSION",
    "SERVER_NAME",
    "SERVER_VERSION",
    "ToolError",
    "ToolSpec",
    "build_default_server",
]
