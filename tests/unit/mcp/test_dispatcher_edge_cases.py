"""Cover the dispatcher's exception branches and Server accessors."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sentinelqa_mcp import MCPServer
from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import SentinelToolset, ToolContext


class _ToolErrorTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.tool_error",
            description="Always raises ToolError.",
            inputSchema={"type": "object"},
        )

    async def invoke(self, args: Mapping[str, Any], ctx: ToolContext) -> AgentEnvelope:
        raise ToolError(
            "E-TEST-001",
            "synthetic",
            exit_code=3,
        )


class _SentinelErrorTool:
    """A tool that raises a SentinelError directly so the dispatcher's
    SentinelError catch branch fires.
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.sentinel_error",
            description="Always raises SentinelError.",
            inputSchema={"type": "object"},
        )

    async def invoke(self, args: Mapping[str, Any], ctx: ToolContext) -> AgentEnvelope:
        from engine.errors.base import InternalError

        raise InternalError("synthetic internal")


class _NoopTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.noop",
            description="No-op.",
            inputSchema={"type": "object"},
        )

    async def invoke(self, args: Mapping[str, Any], ctx: ToolContext) -> AgentEnvelope:
        return success("sentinel.noop", {"ok": True})


def _make_server(*, project: Path) -> MCPServer:
    from sentinelqa import Sentinel

    (project / "sentinel.config.yaml").write_text(
        "version: 1\n"
        "project:\n  name: p\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts:\n    - localhost\n"
        "modules:\n  functional: true\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    sdk = Sentinel(project_path=project, machine_readable=True)
    toolset = SentinelToolset(
        tools=(_ToolErrorTool(), _SentinelErrorTool(), _NoopTool()),
    )
    return MCPServer(
        toolset=toolset,
        context=ToolContext(sentinel=sdk, project_path=project),
    )


async def test_dispatcher_translates_tool_error_to_envelope(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "sentinel.tool_error", "arguments": {}},
        }
    )
    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["result"] is None
    assert payload["errors"][0]["code"] == "E-TEST-001"
    assert payload["errors"][0]["exit_code"] == 3


async def test_dispatcher_translates_sentinel_error_to_envelope(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "sentinel.sentinel_error", "arguments": {}},
        }
    )
    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["result"] is None
    assert payload["errors"][0]["exit_code"] == 7


async def test_dispatcher_returns_tool_call_success(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "sentinel.noop", "arguments": {}},
        }
    )
    assert response is not None
    assert response["result"]["isError"] is False


async def test_server_serve_with_empty_stdio(tmp_path: Path) -> None:
    """``MCPServer.serve`` drives the transport until the peer closes."""

    import io

    from sentinelqa_mcp.transport import StdioTransport

    server = _make_server(project=tmp_path)
    reader = io.StringIO("")  # immediate EOF
    writer = io.StringIO()
    transport = StdioTransport(reader=reader, writer=writer)
    await server.serve(transport)
    assert writer.getvalue() == ""


async def test_server_accessor_properties(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    assert server.toolset is server._toolset
    assert server.context is server._context


async def test_tools_call_requires_name(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {},
        }
    )
    assert response is not None
    assert response["error"]["code"] == -32602


async def test_tools_call_arguments_must_be_object(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "sentinel.noop", "arguments": "not-an-object"},
        }
    )
    assert response is not None
    assert response["error"]["code"] == -32602


async def test_notification_unknown_method_drops_silently(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch({"jsonrpc": "2.0", "method": "wat"})
    assert response is None


async def test_invalid_jsonrpc_with_id_string(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch({"jsonrpc": "1.9", "id": "abc", "method": "ping"})
    assert response is not None
    assert response["id"] == "abc"


async def test_invalid_jsonrpc_without_id_returns_null_id(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    # ValidationError due to bad jsonrpc version + no id → response id None.
    response = await server.dispatch({"jsonrpc": "1.5", "method": "ping"})
    assert response is not None
    assert response["id"] is None


async def test_tools_call_unknown_name(tmp_path: Path) -> None:
    server = _make_server(project=tmp_path)
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "sentinel.does_not_exist", "arguments": {}},
        }
    )
    assert response is not None
    assert response["error"]["code"] == -32601
