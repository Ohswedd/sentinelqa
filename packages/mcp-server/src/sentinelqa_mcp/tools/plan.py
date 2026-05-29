"""``sentinel.plan`` — generate a deterministic test plan."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools._safety import enforce_url


class PlanTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.plan",
            description=(
                "Build a deterministic TestPlan from a fresh crawl of `url`. "
                "Returns the planned flows and coverage estimate. Read-only."
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
        plan = await context.sentinel.async_plan(url=url)
        payload = {
            "plan_id": plan.id,
            "flow_count": len(plan.flows),
            "flows": [
                {
                    "id": flow.id,
                    "name": flow.name,
                    "priority": flow.priority,
                    "extractor": flow.extractor,
                }
                for flow in plan.flows
            ],
        }
        return success("sentinel.plan", payload)


__all__ = ["PlanTool"]
