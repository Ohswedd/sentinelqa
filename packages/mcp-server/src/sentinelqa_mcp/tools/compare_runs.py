# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""``sentinel.compare_runs`` — diff two completed runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engine.runs import compare_runs, load_run_summary

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext


class CompareRunsTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.compare_runs",
            description=(
                "Diff two SentinelQA runs and return the regressions / "
                "improvements. Pass ``before_run_id`` and ``after_run_id`` "
                "(or set ``after_latest=true`` to compare against the most "
                "recent run). Returns: new findings, resolved findings, "
                "persistent findings, severity regressions / improvements, "
                "and the quality-score delta."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "before_run_id": {"type": "string"},
                    "after_run_id": {"type": "string"},
                    "after_latest": {"type": "boolean", "default": False},
                },
                "required": ["before_run_id"],
            },
            **{"_meta": {"read_only": True}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        before_id = arguments.get("before_run_id")
        after_id = arguments.get("after_run_id")
        after_latest = bool(arguments.get("after_latest", False))

        if not isinstance(before_id, str) or not before_id:
            raise ToolError(
                "E-CFG-001",
                "``before_run_id`` is required.",
                exit_code=2,
                suggested_fix="Pass an existing run id, e.g. 'RUN-XXXXXXXXAAAA'.",
            )
        if not after_latest and (not isinstance(after_id, str) or not after_id):
            raise ToolError(
                "E-CFG-001",
                "Pass ``after_run_id`` or set ``after_latest=true``.",
                exit_code=2,
                suggested_fix="Provide one of the two arguments.",
            )

        before_dir = await context.sentinel.async_report(run_id=before_id, latest=False)
        after_dir = await context.sentinel.async_report(
            run_id=after_id if isinstance(after_id, str) else None,
            latest=after_latest,
        )

        before_summary = load_run_summary(before_dir)
        after_summary = load_run_summary(after_dir)
        diff = compare_runs(before_summary, after_summary)

        payload: dict[str, Any] = {
            "before_run_id": diff.before_run_id,
            "after_run_id": diff.after_run_id,
            "score_delta": diff.score_delta,
            "has_regressions": diff.has_regressions,
            "severity_counts_before": diff.severity_counts_before,
            "severity_counts_after": diff.severity_counts_after,
            "new": [_finding_dict(f) for f in diff.new],
            "resolved": [_finding_dict(f) for f in diff.resolved],
            "persistent_count": len(diff.persistent),
            "severity_regressions": [
                {
                    "module": c.after.module,
                    "title": c.after.title,
                    "before": c.before.severity,
                    "after": c.after.severity,
                }
                for c in diff.severity_changes
                if c.direction == "regressed"
            ],
            "severity_improvements": [
                {
                    "module": c.after.module,
                    "title": c.after.title,
                    "before": c.before.severity,
                    "after": c.after.severity,
                }
                for c in diff.severity_changes
                if c.direction == "improved"
            ],
        }
        return success(
            "sentinel.compare_runs",
            payload,
            evidence_refs=(before_dir.name, after_dir.name),
        )


def _finding_dict(f: Any) -> dict[str, str]:
    return {
        "id": f.id,
        "module": f.module,
        "category": f.category,
        "severity": f.severity,
        "title": f.title,
        "code": f.code,
    }


__all__ = ["CompareRunsTool"]
