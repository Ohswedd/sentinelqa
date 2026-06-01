"""``sentinel.accessibility_audit`` — axe-core + deterministic a11y checks."""

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


class AccessibilityAuditTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.accessibility_audit",
            description=(
                "Run axe-core + deterministic a11y checks against `url`. "
                "Reports automated findings only — never claims full WCAG "
                "compliance."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "routes": {"type": "array", "items": {"type": "string"}},
                    "axe_tags": {"type": "array", "items": {"type": "string"}},
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
        axe_tags = arguments.get("axe_tags")
        module_options: dict[str, dict[str, Any]] = {}
        a11y_opts: dict[str, Any] = {}
        if isinstance(routes, list) and routes:
            a11y_opts["routes"] = list(routes)
        if isinstance(axe_tags, list) and axe_tags:
            a11y_opts["axe_tags"] = list(axe_tags)
        if a11y_opts:
            module_options["accessibility"] = a11y_opts
        enforce_url(url, context)
        result = await context.sentinel.async_audit(
            url=url,
            modules=("accessibility",),
            module_options=module_options,
        )
        return success(
            "sentinel.accessibility_audit",
            audit_result_to_payload(result),
            evidence_refs=collect_evidence_refs(result),
        )


__all__ = ["AccessibilityAuditTool"]
