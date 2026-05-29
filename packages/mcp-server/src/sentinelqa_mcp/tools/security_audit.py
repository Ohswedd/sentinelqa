"""``sentinel.security_audit`` — run the safe security module only."""

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


class SecurityAuditTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.security_audit",
            description=(
                "Run the safe security check set against `url` (headers, "
                "cookies, CORS, CSRF, frontend secrets). Destructive probes "
                "require explicit config opt-in + proof-of-authorization."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "checks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Subset of security checks (default: every safe check).",
                    },
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
        checks = arguments.get("checks")
        module_options: dict[str, dict[str, Any]] = {}
        if isinstance(checks, list) and checks:
            module_options["security"] = {"checks": list(checks)}
        enforce_url(url, context)
        result = await context.sentinel.async_audit(
            url=url,
            modules=("security",),
            module_options=module_options,
        )
        return success(
            "sentinel.security_audit",
            audit_result_to_payload(result),
            evidence_refs=collect_evidence_refs(result),
        )


__all__ = ["SecurityAuditTool"]
