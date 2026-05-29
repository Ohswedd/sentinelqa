"""``sentinel.explain_failure`` — surface analyzer output for a specific finding."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext


class ExplainFailureTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.explain_failure",
            description=(
                "Explain a finding from a prior run: category, root-cause "
                "hypothesis, suggested next actions. Reads findings.json "
                "from the named run directory (read-only)."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "run_id": {"type": "string"},
                    "latest": {"type": "boolean", "default": False},
                    "finding_id": {"type": "string"},
                },
                "required": ["finding_id"],
            },
            **{"_meta": {"read_only": True}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        finding_id = arguments.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            raise ToolError(
                "E-CFG-002",
                "Missing 'finding_id'",
                exit_code=2,
                suggested_fix="Pass `finding_id=FND-...`.",
            )
        run_id = arguments.get("run_id")
        latest = bool(arguments.get("latest", False)) or run_id is None
        run_dir = await context.sentinel.async_report(
            run_id=run_id if isinstance(run_id, str) else None,
            latest=latest,
        )
        findings_path = run_dir / "findings.json"
        if not findings_path.is_file():
            raise ToolError(
                "E-FILE-001",
                f"findings.json not found in {run_dir.name}",
                exit_code=3,
                suggested_fix="Run sentinel.audit first.",
            )
        try:
            document = json.loads(findings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError(
                "E-FILE-002",
                f"findings.json is not valid JSON: {exc}",
                exit_code=3,
                suggested_fix="Re-run the audit; the report writer is idempotent.",
            ) from exc
        items = document.get("findings", []) if isinstance(document, dict) else []
        target = next((f for f in items if isinstance(f, dict) and f.get("id") == finding_id), None)
        if target is None:
            raise ToolError(
                "E-FILE-001",
                f"Finding {finding_id!r} not present in {run_dir.name}",
                exit_code=3,
                suggested_fix="Call sentinel.read_report to inspect findings.json.",
            )
        explanation = {
            "run_id": run_dir.name,
            "finding": target,
            "category": target.get("category"),
            "severity": target.get("severity"),
            "module": target.get("module"),
            "recommendation": target.get("recommendation"),
            "evidence_paths": target.get("evidence_paths") or target.get("evidence") or [],
        }
        return success(
            "sentinel.explain_failure",
            explanation,
            evidence_refs=("findings.json",),
        )


__all__ = ["ExplainFailureTool"]
