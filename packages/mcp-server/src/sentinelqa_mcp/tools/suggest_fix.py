"""``sentinel.suggest_fix`` — return the deterministic remediation for a finding.

The Healer module (Phase 20) supplies its own concrete patch
proposals. Until then, this tool returns the deterministic
``recommendation`` + ``suggested_fix`` already attached to the finding
by its emitting module. This is honest: SentinelQA is the *verifier*;
the agent applies the fix; ``sentinel.verify_fix`` confirms.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext


class SuggestFixTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.suggest_fix",
            description=(
                "Return the deterministic remediation for a finding. The "
                "agent applies the fix; sentinel.verify_fix confirms. "
                "Read-only — never edits files."
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
        document = json.loads(findings_path.read_text(encoding="utf-8"))
        items = document.get("findings", []) if isinstance(document, dict) else []
        target = next((f for f in items if isinstance(f, dict) and f.get("id") == finding_id), None)
        if target is None:
            raise ToolError(
                "E-FILE-001",
                f"Finding {finding_id!r} not present in {run_dir.name}",
                exit_code=3,
                suggested_fix="List findings via sentinel.read_report.",
            )
        suggestion = {
            "finding_id": finding_id,
            "recommendation": target.get("recommendation") or "",
            "suggested_fix": target.get("suggested_fix") or "",
            "requires_human_review": True,
            "next_steps": [
                "Apply the recommendation locally.",
                "Call sentinel.verify_fix with this finding_id to confirm.",
            ],
        }
        return success(
            "sentinel.suggest_fix",
            suggestion,
            evidence_refs=("findings.json",),
        )


__all__ = ["SuggestFixTool"]
