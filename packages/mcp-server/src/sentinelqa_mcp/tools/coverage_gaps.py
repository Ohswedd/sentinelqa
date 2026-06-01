# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""``sentinel.coverage_gaps`` — uncovered routes / forms / APIs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from engine.runs import find_coverage_gaps

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext


class CoverageGapsTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.coverage_gaps",
            description=(
                "Return routes / forms / API endpoints that were "
                "discovered by ``sentinel discover`` but have no "
                "corresponding test coverage in the latest run, ranked by "
                "risk (1..5). Pass ``run_id`` (or ``latest=true``); "
                "optionally ``limit`` to cap the response."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "run_id": {"type": "string"},
                    "latest": {"type": "boolean", "default": True},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 25},
                },
            },
            **{"_meta": {"read_only": True}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        run_id = arguments.get("run_id")
        latest = bool(arguments.get("latest", True))
        limit = int(arguments.get("limit") or 25)

        run_dir = await context.sentinel.async_report(
            run_id=run_id if isinstance(run_id, str) else None,
            latest=latest or run_id is None,
        )
        discovery_path = run_dir / "discovery.json"
        if not discovery_path.is_file():
            raise ToolError(
                "E-FILE-001",
                f"No discovery.json under {run_dir.name}",
                exit_code=3,
                suggested_fix="Run sentinel discover before asking for coverage gaps.",
            )

        try:
            discovery_payload = json.loads(discovery_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError(
                "E-FILE-002",
                f"discovery.json is malformed: {exc}",
                exit_code=3,
                suggested_fix="Re-run sentinel discover.",
            ) from exc

        covered_routes, covered_forms, covered_endpoints = _read_coverage_sets(run_dir)

        report = find_coverage_gaps(
            discovery_payload,
            covered_routes=covered_routes,
            covered_forms=covered_forms,
            covered_api_endpoints=covered_endpoints,
        )
        gaps = report.gaps[:limit]
        payload: dict[str, Any] = {
            "run_id": run_dir.name,
            "discovered_total": report.discovered_total,
            "covered_total": report.covered_total,
            "coverage_ratio": round(report.coverage_ratio, 3),
            "gaps": [
                {
                    "kind": gap.kind,
                    "identifier": gap.identifier,
                    "risk_score": gap.risk_score,
                    "rationale": gap.rationale,
                }
                for gap in gaps
            ],
        }
        return success(
            "sentinel.coverage_gaps",
            payload,
            evidence_refs=(discovery_path.name,),
        )


def _read_coverage_sets(run_dir: Any) -> tuple[list[str], list[str], list[str]]:
    """Load coverage sets from any ``coverage.json`` the lifecycle wrote."""

    coverage_path = run_dir / "coverage.json"
    if not coverage_path.is_file():
        return [], [], []
    try:
        payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], [], []
    routes = payload.get("covered_routes") or []
    forms = payload.get("covered_forms") or []
    endpoints = payload.get("covered_api_endpoints") or []
    return (
        [str(x) for x in routes if isinstance(x, str)],
        [str(x) for x in forms if isinstance(x, str)],
        [str(x) for x in endpoints if isinstance(x, str)],
    )


__all__ = ["CoverageGapsTool"]
