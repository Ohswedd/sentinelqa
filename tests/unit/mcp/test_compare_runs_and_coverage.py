# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the v1.4.0 read-only MCP tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinelqa_mcp.tools import ToolContext
from sentinelqa_mcp.tools.compare_runs import CompareRunsTool
from sentinelqa_mcp.tools.coverage_gaps import CoverageGapsTool


class _StubSentinel:
    """Just enough surface to satisfy ``ToolContext.sentinel.async_report``."""

    def __init__(self, run_dirs: dict[str, Path], latest: Path | None = None) -> None:
        self._run_dirs = run_dirs
        self._latest = latest

    async def async_report(self, *, run_id: str | None = None, latest: bool = False):
        if latest:
            assert self._latest is not None, "test set latest=False but tool requested latest"
            return self._latest
        assert run_id is not None
        return self._run_dirs[run_id]


def _write_run(path: Path, *, run_id: str, quality: float, findings: list[dict]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "passed",
                "quality_score": quality,
                "modules_run": ["security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (path / "findings.json").write_text(
        json.dumps({"findings": findings}),
        encoding="utf-8",
    )
    (path / "score.json").write_text("{}", encoding="utf-8")


def _f(severity: str = "high", title: str = "CSP missing") -> dict:
    return {
        "id": f"FND-AAAAAAAAA{severity[:2].upper()}",
        "module": "security",
        "category": "headers",
        "severity": severity,
        "title": title,
        "evidence": {"rule_id": "SEC-HEADERS-CSP-MISSING"},
    }


# --------------------------------------------------------------------------- #
# compare_runs
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_compare_runs_returns_new_finding(tmp_path: Path) -> None:
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_run(before_dir, run_id="RUN-BEFOREAAAAA", quality=85.0, findings=[])
    _write_run(
        after_dir,
        run_id="RUN-AFTERRAAAAA",
        quality=70.0,
        findings=[_f()],
    )
    sentinel = _StubSentinel(
        run_dirs={"RUN-BEFOREAAAAA": before_dir, "RUN-AFTERRAAAAA": after_dir},
    )
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CompareRunsTool()
    env = await tool.invoke(
        {"before_run_id": "RUN-BEFOREAAAAA", "after_run_id": "RUN-AFTERRAAAAA"},
        context,
    )
    payload = env.result
    assert isinstance(payload, dict)
    assert payload["has_regressions"] is True
    assert len(payload["new"]) == 1
    assert payload["score_delta"] == -15.0


@pytest.mark.asyncio
async def test_compare_runs_requires_before_run_id(tmp_path: Path) -> None:
    sentinel = _StubSentinel(run_dirs={})
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CompareRunsTool()
    with pytest.raises(Exception) as exc_info:
        await tool.invoke({}, context)
    assert "before_run_id" in str(exc_info.value)


@pytest.mark.asyncio
async def test_compare_runs_accepts_after_latest_flag(tmp_path: Path) -> None:
    before_dir = tmp_path / "before"
    latest_dir = tmp_path / "latest"
    _write_run(before_dir, run_id="RUN-BEFOREAAAAA", quality=90.0, findings=[_f()])
    _write_run(latest_dir, run_id="RUN-LATESTAAAAA", quality=88.0, findings=[])
    sentinel = _StubSentinel(
        run_dirs={"RUN-BEFOREAAAAA": before_dir},
        latest=latest_dir,
    )
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CompareRunsTool()
    env = await tool.invoke(
        {"before_run_id": "RUN-BEFOREAAAAA", "after_latest": True},
        context,
    )
    result = env.result
    assert isinstance(result, dict)
    assert result["after_run_id"] == "RUN-LATESTAAAAA"
    assert len(result["resolved"]) == 1


# --------------------------------------------------------------------------- #
# coverage_gaps
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_coverage_gaps_returns_uncovered_routes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run(run_dir, run_id="RUN-LATESTAAAAA", quality=80.0, findings=[])
    (run_dir / "discovery.json").write_text(
        json.dumps(
            {
                "graph": {
                    "routes": [
                        {"path": "/", "auth_required": False},
                        {"path": "/admin", "auth_required": True},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    sentinel = _StubSentinel(run_dirs={}, latest=run_dir)
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CoverageGapsTool()
    env = await tool.invoke({"latest": True}, context)
    payload = env.result
    assert isinstance(payload, dict)
    assert payload["discovered_total"] == 2
    assert payload["covered_total"] == 0
    assert any(gap["identifier"] == "/admin" for gap in payload["gaps"])


@pytest.mark.asyncio
async def test_coverage_gaps_respects_limit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run(run_dir, run_id="RUN-LATESTAAAAA", quality=80.0, findings=[])
    routes = [{"path": f"/r{i}", "auth_required": False} for i in range(50)]
    (run_dir / "discovery.json").write_text(
        json.dumps({"graph": {"routes": routes}}), encoding="utf-8"
    )
    sentinel = _StubSentinel(run_dirs={}, latest=run_dir)
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CoverageGapsTool()
    env = await tool.invoke({"latest": True, "limit": 5}, context)
    result = env.result
    assert isinstance(result, dict)
    assert len(result["gaps"]) == 5


@pytest.mark.asyncio
async def test_coverage_gaps_missing_discovery_raises(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run(run_dir, run_id="RUN-LATESTAAAAA", quality=80.0, findings=[])
    sentinel = _StubSentinel(run_dirs={}, latest=run_dir)
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CoverageGapsTool()
    with pytest.raises(Exception) as exc_info:
        await tool.invoke({"latest": True}, context)
    assert "discovery" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_coverage_gaps_reads_covered_set_from_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run(run_dir, run_id="RUN-LATESTAAAAA", quality=80.0, findings=[])
    (run_dir / "discovery.json").write_text(
        json.dumps(
            {
                "graph": {
                    "routes": [
                        {"path": "/", "auth_required": False},
                        {"path": "/admin", "auth_required": True},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "coverage.json").write_text(
        json.dumps({"covered_routes": ["/"]}),
        encoding="utf-8",
    )
    sentinel = _StubSentinel(run_dirs={}, latest=run_dir)
    context = ToolContext(sentinel=sentinel, project_path=tmp_path)  # type: ignore[arg-type]
    tool = CoverageGapsTool()
    env = await tool.invoke({"latest": True}, context)
    result = env.result
    assert isinstance(result, dict)
    assert result["covered_total"] == 1
    assert all(gap["identifier"] != "/" for gap in result["gaps"])


def test_both_tools_register_with_defaults() -> None:
    """The two new tools must appear in the production toolset."""

    from sentinelqa_mcp.tools import SentinelToolset

    toolset = SentinelToolset.with_defaults()
    names = set(toolset.names())
    assert "sentinel.compare_runs" in names
    assert "sentinel.coverage_gaps" in names
