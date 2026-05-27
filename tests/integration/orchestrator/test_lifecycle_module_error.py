"""A module raising mid-run does NOT crash the run."""

from __future__ import annotations

from pathlib import Path

from engine.config.loader import load_config
from engine.errors.base import TestExecutionError
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return p


def test_module_error_captured_not_crashed(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = ModuleRegistry()

    def explode(cfg, decision):
        raise TestExecutionError(detail="explosion in module")

    registry.register_module("functional", explode)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, requested_modules=["functional"])

    # Module crashed → run is `incomplete` (CLAUDE §10 honesty), not `failed`.
    assert test_run.status == "incomplete"
    assert "functional" in test_run.modules_run


def test_module_arbitrary_exception_handled(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = ModuleRegistry()

    def explode(cfg, decision):
        raise RuntimeError("uncategorized")

    registry.register_module("functional", explode)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, requested_modules=["functional"])
    assert test_run.status == "incomplete"
