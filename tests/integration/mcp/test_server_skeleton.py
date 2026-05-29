"""Task 18.01 — MCP server boots, lists tools, and answers ping.

Drives the dispatcher in-process rather than spawning a subprocess so
tests stay fast and deterministic. The wire bytes flowing through
``MCPServer.dispatch`` are identical to what a stdio transport would
read off the line.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from sentinelqa_mcp import (
    AGENT_ENVELOPE_SCHEMA_VERSION,
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    MCPServer,
)


async def _send(server: MCPServer, payload: dict[str, Any]) -> dict[str, Any]:
    response = await server.dispatch(payload)
    assert response is not None, "expected a response (not a notification)"
    return response


async def test_initialize_returns_server_info(server: MCPServer) -> None:
    response = await _send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": MCP_PROTOCOL_VERSION, "clientInfo": {"name": "pytest"}},
        },
    )
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    result = response["result"]
    assert result["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == SERVER_NAME
    assert result["serverInfo"]["version"] == SERVER_VERSION
    assert "tools" in result["capabilities"]


async def test_initialize_rejects_unknown_protocol_version(server: MCPServer) -> None:
    response = await _send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "1999-01-01"},
        },
    )
    assert response["error"]["code"] == -32602
    assert response["error"]["data"]["requested"] == "1999-01-01"


async def test_tools_list_includes_all_twelve_prd_tools(server: MCPServer) -> None:
    response = await _send(
        server,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    )
    names = {tool["name"] for tool in response["result"]["tools"]}
    expected = {
        "sentinel.discover",
        "sentinel.plan",
        "sentinel.generate_tests",
        "sentinel.run_tests",
        "sentinel.audit",
        "sentinel.security_audit",
        "sentinel.performance_audit",
        "sentinel.accessibility_audit",
        "sentinel.read_report",
        "sentinel.explain_failure",
        "sentinel.suggest_fix",
        "sentinel.verify_fix",
    }
    # PRD §16.1 + ping (health check, ADR-0023).
    assert expected.issubset(names)
    assert "sentinel.ping" in names


async def test_ping_round_trip(server: MCPServer) -> None:
    call = await _send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "sentinel.ping", "arguments": {}},
        },
    )
    assert call["result"]["isError"] is False
    assert call["result"]["_meta"]["agent_envelope_schema_version"] == AGENT_ENVELOPE_SCHEMA_VERSION
    envelope = json.loads(call["result"]["content"][0]["text"])
    assert envelope["tool"] == "sentinel.ping"
    assert envelope["result"]["status"] == "ok"
    assert envelope["result"]["server"] == SERVER_NAME
    assert envelope["errors"] == []


async def test_unknown_method_returns_method_not_found(server: MCPServer) -> None:
    response = await _send(
        server,
        {"jsonrpc": "2.0", "id": 5, "method": "tools/forgotten"},
    )
    assert response["error"]["code"] == -32601


async def test_notifications_initialized_drops_silently(server: MCPServer) -> None:
    response = await server.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert response is None


async def test_jsonrpc_protocol_version_mandatory(server: MCPServer) -> None:
    bad = await server.dispatch({"jsonrpc": "1.0", "id": 6, "method": "ping"})
    assert bad is not None
    assert bad["error"]["code"] == -32600


@pytest.mark.parametrize(
    "method",
    [
        "tools/list",
        "ping",
    ],
)
async def test_methods_round_trip_with_string_id(server: MCPServer, method: str) -> None:
    response = await _send(server, {"jsonrpc": "2.0", "id": "abc", "method": method})
    assert response["id"] == "abc"
