"""MCP server dispatcher (ADR-0023).

The server is transport-agnostic: it takes a JSON-RPC 2.0 dict, decides
what to do with it, and returns a JSON-RPC response dict (or ``None``
for notifications). Transports (stdio, loopback HTTP) drive
:meth:`MCPServer.serve` and translate to/from wire bytes.

The dispatcher implements just enough of the MCP `2024-11-05` spec to
support the our product spec tool surface:

- ``initialize`` — handshake, capability negotiation.
- ``notifications/initialized`` — client says it's ready (we observe).
- ``tools/list`` — return the registered :class:`ToolSpec` set.
- ``tools/call`` — invoke a tool, wrap the result in an
 :class:`AgentEnvelope`, return as an MCP ``content`` block.
- ``ping`` — round-trip health check.

Unknown / not-implemented methods raise JSON-RPC ``-32601``
(method-not-found); malformed params raise ``-32602``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from engine.errors.base import SentinelError
from pydantic import ValidationError

from sentinelqa_mcp.envelope import AGENT_ENVELOPE_SCHEMA_VERSION, failure
from sentinelqa_mcp.errors import (
    JSONRPC_APPLICATION_ERROR,
    JSONRPC_INTERNAL_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INVALID_REQUEST,
    JSONRPC_METHOD_NOT_FOUND,
    ToolError,
)
from sentinelqa_mcp.protocol import (
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    SUPPORTED_MCP_PROTOCOL_VERSIONS,
    JSONRPCRequest,
    ToolSpec,
)
from sentinelqa_mcp.tools import SentinelToolset, ToolContext
from sentinelqa_mcp.transport import RequestHandler, Transport

_LOG = logging.getLogger("sentinelqa.mcp")


class MCPServer:
    """Process-local MCP dispatcher.

    Construct with a :class:`SentinelToolset` (the registered tools) and
    a :class:`ToolContext` (the project root + config path the tools
    operate against). One server instance handles many requests
    sequentially within a transport's loop.
    """

    def __init__(
        self,
        toolset: SentinelToolset,
        context: ToolContext,
    ) -> None:
        self._toolset = toolset
        self._context = context
        self._initialized = False
        self._client_info: dict[str, Any] | None = None

    @property
    def toolset(self) -> SentinelToolset:
        return self._toolset

    @property
    def context(self) -> ToolContext:
        return self._context

    async def serve(self, transport: Transport) -> None:
        """Drive ``transport`` until the peer closes."""

        handler: RequestHandler = self.dispatch
        await transport.serve(handler)

    async def dispatch(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        """Decode + dispatch a single JSON-RPC message.

        Returns the response dict, or ``None`` for notifications.
        """

        try:
            request = JSONRPCRequest.model_validate(dict(message))
        except ValidationError as exc:
            # The message itself is malformed. Reply if we can pluck an
            # id, otherwise drop on the floor (per JSON-RPC 2.0).
            req_id = message.get("id") if isinstance(message, Mapping) else None
            return _error_response(
                req_id,
                JSONRPC_INVALID_REQUEST,
                "Invalid JSON-RPC 2.0 request",
                data={"errors": [_describe_validation_error(exc)]},
            )

        try:
            result = await self._handle(request)
        except ToolError as exc:  # pragma: no cover - tools wrap their own errors
            if request.is_notification:
                return None
            return _error_response(
                request.id,
                JSONRPC_APPLICATION_ERROR,
                exc.code,
                data=exc.to_agent_message(),
            )
        except SentinelError as exc:  # pragma: no cover - tools wrap their own errors
            if request.is_notification:
                return None
            return _error_response(
                request.id,
                JSONRPC_APPLICATION_ERROR,
                exc.code,
                data=exc.to_agent_message(),
            )
        except _RPCError as exc:
            if request.is_notification:
                return None
            return _error_response(request.id, exc.code, exc.message, data=exc.data)
        except Exception as exc:  # pragma: no cover - defensive net
            _LOG.exception("Unhandled MCP dispatcher exception: %s", exc)
            if request.is_notification:
                return None
            return _error_response(
                request.id,
                JSONRPC_INTERNAL_ERROR,
                "Internal MCP server error",
                data={"reason": type(exc).__name__},
            )

        if request.is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": result,
        }

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    async def _handle(self, req: JSONRPCRequest) -> dict[str, Any] | list[Any]:
        method = req.method
        params: dict[str, Any] = {}
        if isinstance(req.params, dict):
            params = dict(req.params)
        elif isinstance(req.params, list):
            raise _RPCError(JSONRPC_INVALID_PARAMS, "Positional params not supported")

        if method == "initialize":
            return self._handle_initialize(params)
        if method == "notifications/initialized":
            self._initialized = True
            return {}
        if method == "notifications/cancelled":
            return {}
        if method == "ping":
            return {}
        if method == "tools/list":
            return self._handle_tools_list()
        if method == "tools/call":
            return await self._handle_tools_call(params)
        raise _RPCError(JSONRPC_METHOD_NOT_FOUND, f"Unknown method {method!r}")

    def _handle_initialize(self, params: Mapping[str, Any]) -> dict[str, Any]:
        protocol = params.get("protocolVersion")
        if protocol is not None and protocol not in SUPPORTED_MCP_PROTOCOL_VERSIONS:
            raise _RPCError(
                JSONRPC_INVALID_PARAMS,
                "Unsupported MCP protocol version",
                data={
                    "requested": protocol,
                    "supported": list(SUPPORTED_MCP_PROTOCOL_VERSIONS),
                },
            )
        client_info = params.get("clientInfo")
        if isinstance(client_info, Mapping):
            self._client_info = dict(client_info)
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "instructions": (
                "SentinelQA MCP server. Twelve sentinel.* tools — see "
                "our product spec Every URL tool enforces SafetyPolicy; unsafe "
                "targets surface as agent-envelope errors with "
                "code=UNSAFE_TARGET. Read-only tools advertise "
                "_meta.read_only=true in tools/list."
            ),
        }

    def _handle_tools_list(self) -> dict[str, Any]:
        specs: list[ToolSpec] = list(self._toolset.list_specs())
        wire_tools: list[dict[str, Any]] = []
        for spec in specs:
            payload = spec.model_dump(mode="json", by_alias=True)
            wire_tools.append(payload)
        return {"tools": wire_tools}

    async def _handle_tools_call(self, params: Mapping[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise _RPCError(JSONRPC_INVALID_PARAMS, "Missing tool 'name'")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, Mapping):
            raise _RPCError(JSONRPC_INVALID_PARAMS, "'arguments' must be an object")
        tool = self._toolset.get(name)
        if tool is None:
            raise _RPCError(JSONRPC_METHOD_NOT_FOUND, f"Unknown tool {name!r}")
        try:
            envelope = await tool.invoke(dict(arguments), self._context)
        except ToolError as exc:
            envelope = failure(name, exc.to_agent_message())
        except SentinelError as exc:
            tool_err = ToolError.from_sentinel_error(exc)
            envelope = failure(name, tool_err.to_agent_message())
        except FileNotFoundError as exc:
            tool_err = ToolError(
                "E-FILE-001",
                f"File or directory not found: {exc}",
                exit_code=3,
                suggested_fix="Check the run_id, then re-run sentinel.audit if needed.",
            )
            envelope = failure(name, tool_err.to_agent_message())
        return {
            "content": [
                {"type": "text", "text": envelope.to_wire()},
            ],
            "isError": envelope.is_error,
            "_meta": {
                "agent_envelope_schema_version": AGENT_ENVELOPE_SCHEMA_VERSION,
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _RPCError(Exception):
    def __init__(self, code: int, message: str, *, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _error_response(
    req_id: Any,
    code: int,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _describe_validation_error(exc: ValidationError) -> dict[str, Any]:
    errors = exc.errors()
    if not errors:
        return {"loc": [], "msg": "", "type": ""}
    first = errors[0]
    return {
        "loc": list(first["loc"]),
        "msg": str(first["msg"]),
        "type": str(first["type"]),
    }


def build_default_server(
    *,
    project_path: str | Path = ".",
    config_path: str | Path | None = None,
) -> MCPServer:
    """Construct an :class:`MCPServer` wired against the production SDK.

    ``project_path`` is the directory the tools treat as the audit root
    (the working tree from which `sentinel.config.yaml` and
    ``.sentinel/runs/`` are resolved). ``config_path`` overrides the
    config path explicitly (default: ``<project>/sentinel.config.yaml``).
    """

    from sentinelqa import Sentinel

    project = Path(project_path).resolve()
    config = Path(config_path).resolve() if config_path is not None else None
    sentinel_sdk = Sentinel(project_path=project, config=config, machine_readable=True)
    context = ToolContext(sentinel=sentinel_sdk, project_path=project)
    toolset = SentinelToolset.with_defaults()
    return MCPServer(toolset=toolset, context=context)


__all__ = [
    "MCPServer",
    "build_default_server",
]
