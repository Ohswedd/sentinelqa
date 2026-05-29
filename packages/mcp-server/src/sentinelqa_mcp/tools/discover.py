"""``sentinel.discover`` — crawl the target and return the discovery graph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools._safety import enforce_url


class DiscoverTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.discover",
            description=(
                "Crawl `url` and return the DiscoveryGraph (routes, forms, "
                "API endpoints, auth boundaries). HTTP-first by default."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                },
                "required": ["url"],
            },
            **{"_meta": {"read_only": True}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        url = arguments.get("url")
        if not isinstance(url, str) or not url:
            raise ToolError(
                "E-CFG-002", "Missing 'url' argument", exit_code=2, suggested_fix="Pass `url=...`."
            )
        enforce_url(url, context)
        graph = await context.sentinel.async_discover(url)
        payload = {
            "graph_id": graph.id,
            "route_count": len(graph.routes),
            "routes": [r.path for r in graph.routes],
        }
        return success("sentinel.discover", payload)


__all__ = ["DiscoverTool"]
