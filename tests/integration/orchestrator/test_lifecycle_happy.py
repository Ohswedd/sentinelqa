"""End-to-end lifecycle: stubbed module factories, all 17 steps reachable."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from engine.orchestrator.registry import ModuleRegistry
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


def test_happy_path_writes_full_artifact_tree(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    config = load_config(config_path)

    artifacts_root = tmp_path / ".sentinel" / "runs"
    registry = ModuleRegistry()
    registry.register_module("functional", lambda cfg, decision: {"ok": True})

    lifecycle = RunLifecycle(artifacts_root=artifacts_root, registry=registry)
    test_run = lifecycle.execute(config)

    assert test_run.status == "passed"
    assert "functional" in test_run.modules_run

    run_dir = artifacts_root / test_run.id
    assert (run_dir / "run.json").exists()
    assert (run_dir / "config.snapshot.yaml").exists()
    assert (run_dir / "audit.log").exists()
    assert (run_dir / "plan.json").exists()

    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "passed"
    assert run_payload["schema_version"] == test_run.SCHEMA_VERSION

    latest = artifacts_root / "latest"
    assert latest.exists() or latest.is_symlink()
