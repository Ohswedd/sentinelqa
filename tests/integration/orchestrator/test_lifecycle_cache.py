# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""End-to-end lifecycle: discovery cache, plan cache, cache.json output."""

from __future__ import annotations

import json
from pathlib import Path

from engine.cache import CacheStore, compute_fingerprint
from engine.cache.run_info import read_cache_report
from engine.config.loader import load_config
from engine.orchestrator.registry import LifecyclePhase, ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle


def _write_config(root: Path) -> Path:
    config_path = root / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: test-app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n",
        encoding="utf-8",
    )
    return config_path


def _project_with_one_source(root: Path) -> Path:
    """Lay out a tiny source tree so the fingerprint has something to hash."""

    src_root = root / "project"
    src_root.mkdir()
    _write_config(src_root)
    (src_root / "src").mkdir()
    (src_root / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    return src_root


def _run_lifecycle(
    *,
    project_root: Path,
    artifacts_root: Path,
    cache_store: CacheStore,
    extra_hook=None,
) -> tuple[str, Path]:
    config = load_config(project_root / "sentinel.config.yaml")
    registry = ModuleRegistry()
    registry.register_module("functional", lambda cfg, decision: {"ok": True})
    if extra_hook is not None:
        registry.register_phase_hook(LifecyclePhase.DISCOVER_APP, extra_hook)
    lifecycle = RunLifecycle(
        artifacts_root=artifacts_root,
        registry=registry,
        project_root=project_root,
        cache_store=cache_store,
    )
    test_run = lifecycle.execute(config)
    return test_run.id, artifacts_root / test_run.id


def test_cache_report_is_written_with_fingerprint(tmp_path: Path) -> None:
    """``cache.json`` must exist and carry the source fingerprint."""

    project = _project_with_one_source(tmp_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    cache = CacheStore(tmp_path / ".sentinel" / "cache")

    _, run_dir = _run_lifecycle(
        project_root=project, artifacts_root=artifacts_root, cache_store=cache
    )

    report = read_cache_report(run_dir / "cache.json")
    assert report is not None
    assert report.source_fingerprint is not None
    assert len(report.source_fingerprint.hash) == 64
    assert report.source_fingerprint.file_count >= 1


def test_plan_cache_misses_on_first_run_hits_on_second(tmp_path: Path) -> None:
    """Two runs over the same source tree: first misses, second hits."""

    project = _project_with_one_source(tmp_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    cache = CacheStore(tmp_path / ".sentinel" / "cache")

    _, run_dir_first = _run_lifecycle(
        project_root=project, artifacts_root=artifacts_root, cache_store=cache
    )
    _, run_dir_second = _run_lifecycle(
        project_root=project, artifacts_root=artifacts_root, cache_store=cache
    )

    first = read_cache_report(run_dir_first / "cache.json")
    second = read_cache_report(run_dir_second / "cache.json")
    assert first is not None and second is not None
    assert first.plan.cache_hit is False
    assert second.plan.cache_hit is True
    assert first.source_fingerprint == second.source_fingerprint


def test_discovery_cache_round_trip_through_hook(tmp_path: Path) -> None:
    """A discovery hook that writes discovery.json must round-trip via the cache."""

    project = _project_with_one_source(tmp_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    cache = CacheStore(tmp_path / ".sentinel" / "cache")

    payload = {"routes": ["/", "/about"], "schema_version": "1"}

    def discovery_hook(ctx) -> None:
        if ctx.discovery_cache_hit:
            return
        ctx.artifacts.write_json("discovery.json", payload)

    _, run_dir_first = _run_lifecycle(
        project_root=project,
        artifacts_root=artifacts_root,
        cache_store=cache,
        extra_hook=discovery_hook,
    )
    # Second run with the same hook — the cache should serve discovery.json.
    _, run_dir_second = _run_lifecycle(
        project_root=project,
        artifacts_root=artifacts_root,
        cache_store=cache,
        extra_hook=discovery_hook,
    )

    first = read_cache_report(run_dir_first / "cache.json")
    second = read_cache_report(run_dir_second / "cache.json")
    assert first is not None and second is not None
    assert first.discovery.cache_hit is False
    assert second.discovery.cache_hit is True
    assert (run_dir_second / "discovery.json").is_file()
    # The cached payload must equal the original hook output byte-for-byte.
    body = json.loads((run_dir_second / "discovery.json").read_text(encoding="utf-8"))
    assert body == payload


def test_plan_cache_invalidates_when_source_changes(tmp_path: Path) -> None:
    """Source content drift must invalidate the plan cache key."""

    project = _project_with_one_source(tmp_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    cache = CacheStore(tmp_path / ".sentinel" / "cache")

    _run_lifecycle(project_root=project, artifacts_root=artifacts_root, cache_store=cache)

    # Drift: change a source file. New fingerprint → new cache key.
    (project / "src" / "main.py").write_text("print('drifted')\n", encoding="utf-8")
    _, run_dir = _run_lifecycle(
        project_root=project, artifacts_root=artifacts_root, cache_store=cache
    )
    report = read_cache_report(run_dir / "cache.json")
    assert report is not None
    assert report.plan.cache_hit is False


def test_fingerprint_matches_independent_computation(tmp_path: Path) -> None:
    """The fingerprint persisted in cache.json must equal what ``compute_fingerprint`` returns."""

    project = _project_with_one_source(tmp_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    cache = CacheStore(tmp_path / ".sentinel" / "cache")

    _, run_dir = _run_lifecycle(
        project_root=project, artifacts_root=artifacts_root, cache_store=cache
    )
    report = read_cache_report(run_dir / "cache.json")
    assert report is not None
    expected = compute_fingerprint(project)
    assert report.source_fingerprint is not None
    assert report.source_fingerprint.hash == expected.hash
    assert report.source_fingerprint.file_count == expected.file_count
