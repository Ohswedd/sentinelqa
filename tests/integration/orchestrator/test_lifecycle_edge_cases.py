"""Edge cases for the run lifecycle to round out coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.errors.base import ConfigError, SentinelError
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import LifecycleContext, RunLifecycle


def _write_all_modules_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "modules:\n  functional: true\n  api: true\n  accessibility: true\n"
        "  performance: true\n  visual: true\n  security: true\n"
        "  chaos: true\n  llm_audit: true\n",
        encoding="utf-8",
    )
    return p


def test_modules_to_run_covers_every_branch(tmp_path: Path) -> None:
    config = load_config(_write_all_modules_config(tmp_path))
    lc = RunLifecycle(artifacts_root=tmp_path / "runs", registry=ModuleRegistry())
    test_run = lc.execute(config)
    # All enabled modules are visited, all "skipped" because none registered.
    assert set(test_run.modules_run) == {
        "functional",
        "api",
        "accessibility",
        "performance",
        "visual",
        "security",
        "chaos",
        "llm_audit",
    }


def test_load_config_rejects_non_root_config(tmp_path: Path) -> None:
    lc = RunLifecycle(artifacts_root=tmp_path / "runs")
    ctx = LifecycleContext(
        config="not a config",
        registry=ModuleRegistry(),
        requested_modules=None,
        dry_run=False,
        ci=False,
    )
    with pytest.raises(ConfigError):
        lc.load_config(ctx)


def test_validate_config_catches_post_load_mutation(tmp_path: Path) -> None:
    cfg = load_config(_write_all_modules_config(tmp_path))
    lc = RunLifecycle(artifacts_root=tmp_path / "runs")
    ctx = LifecycleContext(
        config=cfg,
        registry=ModuleRegistry(),
        requested_modules=None,
        dry_run=False,
        ci=False,
    )
    # Replace the config with something that fails RootConfig validation.
    bad_cfg = type("Bad", (), {"to_dict": lambda self: {"version": "not-an-int"}})()
    ctx.config = bad_cfg
    with pytest.raises(ConfigError):
        lc.validate_config(ctx)


def test_persist_artifacts_includes_findings_and_score(tmp_path: Path) -> None:
    cfg = load_config(_write_all_modules_config(tmp_path))
    registry = ModuleRegistry()

    from engine.orchestrator.registry import LifecyclePhase

    def add_findings(ctx) -> None:
        ctx.findings.append({"id": "FND-001"})

    def add_score(ctx) -> None:
        ctx.quality_score = {"score": 99}

    registry.register_phase_hook(LifecyclePhase.NORMALIZE_FINDINGS, add_findings)
    registry.register_phase_hook(LifecyclePhase.CALCULATE_QUALITY_SCORE, add_score)

    lc = RunLifecycle(artifacts_root=tmp_path / "runs", registry=registry)
    tr = lc.execute(cfg)
    run_dir = tmp_path / "runs" / tr.id
    assert (run_dir / "findings.json").exists()
    assert (run_dir / "score.json").exists()
    findings = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["findings"][0]["id"] == "FND-001"


def test_module_raises_sentinel_error_subclass(tmp_path: Path) -> None:
    cfg = load_config(_write_all_modules_config(tmp_path))
    registry = ModuleRegistry()

    class CustomError(SentinelError):
        DEFAULT_CODE = "E-RUN-001"

    def explode(c, d):
        raise CustomError(detail="custom")

    registry.register_module("functional", explode)
    lc = RunLifecycle(
        artifacts_root=tmp_path / "runs",
        registry=registry,
    )
    tr = lc.execute(cfg, requested_modules=["functional"])
    assert tr.status == "incomplete"
