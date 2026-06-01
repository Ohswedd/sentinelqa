"""``sentinel.suggest_fix`` — return remediation for a finding.

When the Healer module has persisted a concrete repair
proposal for the run, this tool returns its full :class:`RepairProposal`
payload (kind, confidence, unified_diff, requires_human_review). When no
healer artifacts are present, it falls back to the finding's
``recommendation`` + ``suggested_fix`` from the emitting module — the
Phase-18 contract. Either way, the agent applies the fix and
``sentinel.verify_fix`` confirms; SentinelQA never mutates source from
the MCP tool surface.
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
        # if the Healer persisted proposals for this run, surface
        # the ones whose target_test matches the finding's location.file.
        from engine.healer.writer import iter_proposals  # local import keeps startup cheap

        location = target.get("location") or {}
        target_file = str(location.get("file") or "")
        healer_proposals: list[dict[str, object]] = []
        for proposal_doc in iter_proposals(run_dir):
            test_path = str(proposal_doc.get("target_test", ""))
            if target_file and target_file in test_path:
                healer_proposals.append(
                    {
                        "id": proposal_doc.get("id"),
                        "kind": proposal_doc.get("kind"),
                        "confidence": proposal_doc.get("confidence"),
                        "target_test": test_path,
                        "unified_diff": proposal_doc.get("unified_diff"),
                        "requires_human_review": proposal_doc.get("requires_human_review"),
                        "reason": proposal_doc.get("reason"),
                    }
                )

        suggestion = {
            "finding_id": finding_id,
            "recommendation": target.get("recommendation") or "",
            "suggested_fix": target.get("suggested_fix") or "",
            "requires_human_review": True,
            "healer_proposals": healer_proposals,
            "next_steps": [
                "Apply one of the healer_proposals (preferred) or the suggested_fix.",
                "Call sentinel.verify_fix with this finding_id to confirm.",
            ],
        }
        return success(
            "sentinel.suggest_fix",
            suggestion,
            evidence_refs=("findings.json",),
        )


__all__ = ["SuggestFixTool"]
