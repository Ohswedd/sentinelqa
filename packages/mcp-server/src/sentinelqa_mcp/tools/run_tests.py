"""``sentinel.run_tests`` — run the functional module against `url`."""

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


class RunTestsTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.run_tests",
            description=(
                "Run the Playwright functional suite against `url`. Returns an "
                "AuditResult restricted to the functional module."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "mode": {
                        "type": "string",
                        "enum": ["smoke", "standard", "full"],
                        "default": "standard",
                    },
                    "grep": {"type": "string"},
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
        mode = arguments.get("mode", "standard")
        if mode not in {"smoke", "standard", "full"}:
            raise ToolError(
                "E-CFG-002",
                f"Invalid mode {mode!r}",
                exit_code=2,
                suggested_fix="Use one of smoke|standard|full.",
            )
        grep = arguments.get("grep")
        module_options: dict[str, dict[str, Any]] = {"functional": {"mode": mode}}
        if isinstance(grep, str) and grep:
            module_options["functional"]["grep"] = grep
        enforce_url(url, context)
        result = await context.sentinel.async_audit(
            url=url,
            modules=("functional",),
            module_options=module_options,
        )
        return success(
            "sentinel.run_tests",
            audit_result_to_payload(result),
            evidence_refs=collect_evidence_refs(result),
        )


__all__ = ["RunTestsTool"]
