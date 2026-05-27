"""Dry-run stops after build_execution_plan."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: dry\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    return p


def test_dry_run_writes_plan_no_modules(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    invoked: list[str] = []
    registry = ModuleRegistry()

    def watcher(cfg, decision):
        invoked.append("functional")
        return

    registry.register_module("functional", watcher)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, dry_run=True)

    assert test_run.status == "dry_run"
    assert invoked == []
    run_dir = tmp_path / ".sentinel" / "runs" / test_run.id
    plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run"] is True
    assert "modules" in plan
