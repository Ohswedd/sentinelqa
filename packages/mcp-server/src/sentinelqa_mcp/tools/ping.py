"""``sentinel.ping`` — health check (task 18.01)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.protocol import SERVER_NAME, SERVER_VERSION, ToolSpec
from sentinelqa_mcp.tools import ToolContext


class PingTool:
    """Returns ``{status, version, server}`` — used by clients to confirm reachability."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.ping",
            description="Health check. Returns the running server name and version.",
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            **{"_meta": {"read_only": True}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        del arguments, context
        return success(
            "sentinel.ping",
            {
                "status": "ok",
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        )


__all__ = ["PingTool"]
