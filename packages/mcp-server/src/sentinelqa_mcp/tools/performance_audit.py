"""``sentinel.performance_audit`` — synthetic perf budgets only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools._audit_helpers import (
    audit_result_to_payload,
    collect_evidence_refs,
)
from sentinelqa_mcp.tools._safety import enforce_url


class PerformanceAuditTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.performance_audit",
            description=(
                "Synthetic performance check against `url` (LCP/CLS/INP/TTFB, "
                "API P95, JS bundle, long tasks, nav stability). Lab "
                "measurements, not RUM."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "routes": {"type": "array", "items": {"type": "string"}},
                    "samples": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["url"],
            },
            **{"_meta": {"read_only": False}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        url = arguments.get("url")
        if not isinstance(url, str) or not url:
            raise ToolError(
                "E-CFG-002", "Missing 'url' argument", exit_code=2, suggested_fix="Pass `url=...`."
            )
        routes = arguments.get("routes")
        samples = arguments.get("samples")
        module_options: dict[str, dict[str, Any]] = {}
        perf_opts: dict[str, Any] = {}
        if isinstance(routes, list) and routes:
            perf_opts["routes"] = list(routes)
        if isinstance(samples, int):
            perf_opts["samples"] = samples
        if perf_opts:
            module_options["performance"] = perf_opts
        enforce_url(url, context)
        result = await context.sentinel.async_audit(
            url=url,
            modules=("performance",),
            module_options=module_options,
        )
        return success(
            "sentinel.performance_audit",
            audit_result_to_payload(result),
            evidence_refs=collect_evidence_refs(result),
        )


__all__ = ["PerformanceAuditTool"]
