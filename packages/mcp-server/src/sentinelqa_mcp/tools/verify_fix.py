"""``sentinel.verify_fix`` — verify an agent-applied fix."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools._safety import enforce_url
from sentinelqa_mcp.verify_fix import run_verify_fix


class VerifyFixTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.verify_fix",
            description=(
                "Verify an agent-applied fix. Re-runs the prior audit against "
                "the current working tree and diffs findings. Returns a "
                "VerifyFixResult with a four-valued decision: fix_verified, "
                "partial, regressed, still_failing."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "run_id": {"type": "string"},
                    "finding_id": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["run_id"],
            },
            **{"_meta": {"read_only": False}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        run_id = arguments.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ToolError(
                "E-CFG-002",
                "Missing 'run_id'",
                exit_code=2,
                suggested_fix="Pass the run id of the prior failing audit.",
            )
        finding_id = arguments.get("finding_id")
        url = arguments.get("url")
        modules_arg = arguments.get("modules")
        modules: tuple[str, ...] | None = None
        if isinstance(modules_arg, list) and modules_arg:
            modules = tuple(str(m) for m in modules_arg)

        if isinstance(url, str) and url:
            enforce_url(url, context)
        result = await run_verify_fix(
            sentinel=context.sentinel,
            run_id=run_id,
            target_finding_id=finding_id if isinstance(finding_id, str) and finding_id else None,
            url=url if isinstance(url, str) and url else None,
            modules=modules,
        )
        payload = {
            "decision": result.decision,
            "target_finding_id": result.target_finding_id,
            "new_run_id": result.new_run_id,
            "fixed_finding_ids": list(result.fixed_finding_ids),
            "unchanged_finding_ids": list(result.unchanged_finding_ids),
            "regression_finding_ids": list(result.regression_finding_ids),
            "summary": result.summary,
        }
        return success("sentinel.verify_fix", payload)


__all__ = ["VerifyFixTool"]
