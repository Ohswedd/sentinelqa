# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the ``sentinel.replay_with_change`` MCP tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools.replay_with_change import ReplayWithChangeTool


class _StubSentinel:
    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    async def async_report(self, *, run_id: str | None = None, latest: bool = False):
        _ = run_id, latest
        return self._run_dir


def _write_run(path: Path, *, run_id: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "passed",
                "quality_score": 90.0,
                "modules_run": ["security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (path / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (path / "score.json").write_text("{}", encoding="utf-8")


@pytest.mark.asyncio
async def test_replay_requires_diff(tmp_path: Path) -> None:
    sentinel = _StubSentinel(tmp_path)
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = ReplayWithChangeTool()
    with pytest.raises(Exception) as exc:
        await tool.invoke({"unified_diff": ""}, context)
    assert "required" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_replay_rejects_oversize_diff(tmp_path: Path) -> None:
    sentinel = _StubSentinel(tmp_path)
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = ReplayWithChangeTool()
    huge = "x" * (64 * 1024 + 1)
    with pytest.raises(Exception) as exc:
        await tool.invoke({"unified_diff": huge}, context)
    assert "cap" in str(exc.value).lower() or "exceeds" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_replay_returns_outcome_with_no_runner(tmp_path: Path) -> None:
    """The tool returns a clean error outcome when no runner is wired."""

    project = tmp_path / "project"
    project.mkdir()
    (project / "src.py").write_text("x = 1\n", encoding="utf-8")
    run_dir = tmp_path / "runs" / "RUN-LATESTAAAAA"
    _write_run(run_dir, run_id="RUN-LATESTAAAAA")
    sentinel = _StubSentinel(run_dir)
    context = ToolContext(sentinel=sentinel, project_path=project)  # type: ignore[arg-type]
    tool = ReplayWithChangeTool()
    diff = "diff --git a/src.py b/src.py\n--- a/src.py\n+++ b/src.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    env = await tool.invoke({"unified_diff": diff, "source_latest": True}, context)
    payload = env.result
    assert isinstance(payload, dict)
    assert "success" in payload


def test_replay_tool_registered_in_defaults() -> None:
    from sentinelqa_mcp.tools import SentinelToolset

    toolset = SentinelToolset.with_defaults()
    assert "sentinel.replay_with_change" in toolset.names()
