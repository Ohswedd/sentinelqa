"""SupplyChainModule lifecycle integration."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision

from modules.supply_chain import SupplyChainModule, register_with_default_registry
from modules.supply_chain.models import SupplyChainRunOutcome
from modules.supply_chain.module import (
    _enabled_check_count,
    _factory,
    _resolve_enabled_checks,
)
from modules.supply_chain.options import SupplyChainModuleOptions


def _write_config(root: Path, body: str = "") -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n  base_url: http://localhost:8088\n  allowed_hosts: [localhost, 127.0.0.1]\n"
        + body,
        encoding="utf-8",
    )
    return p


def _make_safety(cfg: Any) -> SafetyDecision:
    return SafetyDecision(
        allowed=True,
        host="localhost",
        reason="local",
        mode=cfg.security.mode,
        decided_at=datetime.now(UTC),
    )


@contextmanager
def _temp_config():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "sentinel.config.yaml"
        path.write_text(
            "version: 1\n"
            "project:\n  name: app\n"
            "target:\n  base_url: http://localhost:8088\n  allowed_hosts: [localhost]\n",
            encoding="utf-8",
        )
        yield load_config(path)


def _build_ctx(tmp_path: Path, options: dict[str, Any] | None = None) -> ModuleContext:
    cfg_path = _write_config(tmp_path)
    config = load_config(cfg_path)
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
    )
    safety = _make_safety(config)
    return ModuleContext(
        module_name="supply_chain",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def test_factory_returns_module() -> None:
    with _temp_config() as cfg:
        module = _factory(cfg, _make_safety(cfg))
        assert isinstance(module, SupplyChainModule)


def test_register_with_default_registry_is_idempotent() -> None:
    from engine.orchestrator.registry import default_registry

    register_with_default_registry()
    before = id(default_registry().modules.get("supply_chain"))
    register_with_default_registry()
    after = id(default_registry().modules.get("supply_chain"))
    assert before == after


def test_resolve_enabled_checks_honours_config(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path,
        "policy:\n  supply_chain:\n    osv:\n      enabled: false\n",
    )
    config = load_config(cfg_path)
    options = SupplyChainModuleOptions()
    enabled = _resolve_enabled_checks(config, options)
    assert "sbom" in enabled
    assert "osv" not in enabled


def test_resolve_enabled_checks_cli_override_intersects(tmp_path: Path) -> None:
    cfg_path = _write_config(tmp_path)
    config = load_config(cfg_path)
    options = SupplyChainModuleOptions(enabled_checks=("sbom", "bogus", "container"))
    enabled = _resolve_enabled_checks(config, options)
    assert "sbom" in enabled
    assert "container" in enabled
    assert "bogus" not in enabled


def test_enabled_check_count_counts_present_sections() -> None:
    outcome = SupplyChainRunOutcome(
        duration_ms=0,
        incomplete=False,
    )
    assert _enabled_check_count(outcome) == 0


def test_run_audit_writes_artifacts_for_empty_project(tmp_path: Path) -> None:
    ctx = _build_ctx(
        tmp_path,
        options={
            "enabled_checks": ("sbom", "freshness"),
        },
    )
    module = SupplyChainModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.status in {"passed", "skipped"}
    assert (ctx.run_dir / "sbom" / "index.json").exists()
    assert (ctx.run_dir / "supply_chain" / "index.json").exists()


def test_run_audit_handles_lockfile(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    ctx = _build_ctx(
        tmp_path,
        options={"project_root": tmp_path, "enabled_checks": ("sbom", "freshness")},
    )
    module = SupplyChainModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.status in {"passed", "skipped"}
    sbom_index = json.loads((ctx.run_dir / "sbom" / "index.json").read_text(encoding="utf-8"))
    assert sbom_index["components_count"] == 1
