"""``sentinel.audit`` — run the canonical audit lifecycle (the documentation)."""

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
    parse_optional_modules,
)
from sentinelqa_mcp.tools._safety import enforce_url


class AuditTool:
    """Run the full audit lifecycle. Mirrors :meth:`sentinel audit`."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.audit",
            description=(
                "Run the canonical SentinelQA audit lifecycle against `url`. "
                "Returns a structured AuditResult with quality score, release "
                "decision, findings, and agent messages. Safe-by-default — "
                "destructive checks require explicit config opt-in."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Subset of modules to run (default: every enabled module).",
                    },
                    "safe_mode": {"type": "boolean", "default": True},
                    "dry_run": {"type": "boolean", "default": False},
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
        modules = parse_optional_modules(arguments)
        safe_mode = bool(arguments.get("safe_mode", True))
        dry_run = bool(arguments.get("dry_run", False))

        enforce_url(url, context)
        result = await context.sentinel.async_audit(
            url=url,
            modules=modules,
            safe_mode=safe_mode,
            dry_run=dry_run,
        )
        payload = audit_result_to_payload(result)
        return success(
            "sentinel.audit",
            payload,
            evidence_refs=collect_evidence_refs(result),
        )


__all__ = ["AuditTool"]
