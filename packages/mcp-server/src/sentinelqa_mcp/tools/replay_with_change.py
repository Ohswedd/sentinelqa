# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""``sentinel.replay_with_change`` — apply a patch + rerun."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from engine.runs.replay import ReplayRequest, replay, summarise_outcome

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext

_MAX_DIFF_LEN: int = 64 * 1024


class ReplayWithChangeTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.replay_with_change",
            description=(
                "Apply a unified-diff patch to an isolated copy of the "
                "working tree, replay the audit run, and return the "
                "findings diff vs the original run. The patch is rejected "
                "if it doesn't apply cleanly. Optional ``test_ids`` "
                "restricts the replay to a subset; ``source_run_id`` picks "
                "the baseline run."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "unified_diff": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": _MAX_DIFF_LEN,
                    },
                    "source_run_id": {"type": "string"},
                    "source_latest": {"type": "boolean", "default": False},
                    "test_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
                "required": ["unified_diff"],
            },
            **{"_meta": {"read_only": False}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        unified_diff = arguments.get("unified_diff")
        if not isinstance(unified_diff, str) or not unified_diff.strip():
            raise ToolError(
                "E-CFG-001",
                "``unified_diff`` is required.",
                exit_code=2,
                suggested_fix="Pass the unified-diff text the patch should apply.",
            )
        if len(unified_diff) > _MAX_DIFF_LEN:
            raise ToolError(
                "E-CFG-001",
                f"``unified_diff`` exceeds the {_MAX_DIFF_LEN}-byte cap.",
                exit_code=2,
                suggested_fix="Split the patch into smaller hunks.",
            )

        source_run_id = arguments.get("source_run_id")
        source_latest = bool(arguments.get("source_latest", False))
        test_ids_raw = arguments.get("test_ids") or []
        test_ids = tuple(str(t) for t in test_ids_raw if isinstance(t, str))

        source_run_dir = await context.sentinel.async_report(
            run_id=source_run_id if isinstance(source_run_id, str) else None,
            latest=source_latest or source_run_id is None,
        )

        request = ReplayRequest(
            source_run_dir=Path(source_run_dir),
            unified_diff=unified_diff,
            project_root=Path(context.project_path),
            test_ids=test_ids,
        )
        # The tool does not own the lifecycle runner — that ships with
        # the SDK. We surface a clear "no-runner" outcome until the
        # SDK exposes its replay seam (tracked separately). The
        # patch / safety machinery still runs end-to-end so agents see
        # whether the diff is even applicable.
        outcome = replay(request)
        return success(
            "sentinel.replay_with_change",
            summarise_outcome(outcome),
            evidence_refs=(source_run_dir.name,),
        )


__all__ = ["ReplayWithChangeTool"]
