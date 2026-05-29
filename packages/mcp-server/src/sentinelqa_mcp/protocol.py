"""Wire-level types for the MCP / JSON-RPC 2.0 protocol (ADR-0023).

The MCP base transport is JSON-RPC 2.0 over NDJSON-framed stdio. This
module defines:

- The JSON-RPC 2.0 request / response / error shapes.
- The :class:`ToolSpec` advertised in ``tools/list``.
- Constants for the SentinelQA server identity and supported MCP
  protocol versions.

Every type here is a frozen Pydantic model so the wire format is
self-validating and deterministic.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

# Public identity bytes (used in the ``initialize`` handshake).
SERVER_NAME: str = "sentinelqa-mcp"
SERVER_VERSION: str = "0.1.0"

# MCP protocol version we speak. ADR-0023 pins us to a single supported
# version so a protocol upgrade is a deliberate change, not silent
# drift.
MCP_PROTOCOL_VERSION: str = "2024-11-05"
SUPPORTED_MCP_PROTOCOL_VERSIONS: tuple[str, ...] = (MCP_PROTOCOL_VERSION,)

JSONRPCVersion = Literal["2.0"]


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: int
    message: str
    data: dict[str, Any] | None = None


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request (or notification, when ``id`` is absent).

    Notifications carry no ``id`` and produce no response.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonrpc: JSONRPCVersion = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | list[Any] | None = None

    @property
    def is_notification(self) -> bool:
        """Notifications have no ``id`` field."""

        return self.id is None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response object. Exactly one of ``result``/``error``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonrpc: JSONRPCVersion = "2.0"
    id: int | str | None
    result: dict[str, Any] | list[Any] | None = None
    error: JSONRPCError | None = None


class ToolSpec(BaseModel):
    """A single MCP tool advertised in ``tools/list``.

    The ``inputSchema`` is a JSON Schema (Draft 2020-12) for the
    arguments map. ``_meta.read_only`` is a SentinelQA extension hinting
    that a tool does not mutate the working tree, audit log, or
    `.sentinel/runs/`. Clients that honor read-only hints (PRD §16
    aligns with the Anthropic MCP spec extension) can refuse to
    sandbox-disable on these calls.
    """

    name: str = Field(pattern=r"^sentinel\.[a-z_]+$")
    description: str
    inputSchema: dict[str, Any]  # noqa: N815 - MCP wire field name
    meta: dict[str, Any] = Field(default_factory=dict, alias="_meta")

    READ_ONLY_META_KEY: ClassVar[str] = "read_only"

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @property
    def read_only(self) -> bool:
        return bool(self.meta.get(self.READ_ONLY_META_KEY, False))


__all__ = [
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCVersion",
    "MCP_PROTOCOL_VERSION",
    "SERVER_NAME",
    "SERVER_VERSION",
    "SUPPORTED_MCP_PROTOCOL_VERSIONS",
    "ToolSpec",
]
