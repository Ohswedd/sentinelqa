"""``sentinel.generate_tests`` — render Playwright specs from a plan."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools._audit_helpers import safe_relative
from sentinelqa_mcp.tools._safety import enforce_url


class GenerateTestsTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.generate_tests",
            description=(
                "Generate Playwright specs, page objects, and fixtures for "
                "`url` under `out_dir` (default: <project>/tests/sentinel)."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "out_dir": {"type": "string"},
                    "force": {"type": "boolean", "default": False},
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
        out_dir_arg = arguments.get("out_dir")
        out_dir = (
            Path(out_dir_arg)
            if isinstance(out_dir_arg, str) and out_dir_arg
            else context.project_path / "tests" / "sentinel"
        )
        force = bool(arguments.get("force", False))

        enforce_url(url, context)
        plan = await context.sentinel.async_plan(url=url)
        written = await context.sentinel.async_generate_tests(
            plan,
            out_dir=out_dir,
            base_url=url,
            force=force,
        )
        payload = {
            "plan_id": plan.id,
            "out_dir": str(out_dir),
            "files": [safe_relative(p, context.project_path) for p in written],
            "file_count": len(written),
        }
        return success("sentinel.generate_tests", payload)


__all__ = ["GenerateTestsTool"]
