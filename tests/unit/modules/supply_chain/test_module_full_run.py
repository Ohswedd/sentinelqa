"""Cover the SupplyChainModule full-lifecycle paths (Phase 33)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision

from modules.supply_chain import SupplyChainModule


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


def _ctx(tmp_path: Path, options: dict | None = None, config_body: str = "") -> ModuleContext:
    cfg = load_config(_write_config(tmp_path, body=config_body))
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    return ModuleContext(
        module_name="supply_chain",
        config=cfg,
        safety_decision=SafetyDecision(
            allowed=True,
            host="localhost",
            reason="local",
            mode=cfg.security.mode,
            decided_at=datetime.now(UTC),
        ),
        artifacts=ArtifactDirectory(run_dir),
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=Target(
            base_url=cfg.target.base_url,
            allowed_hosts=frozenset(cfg.target.allowed_hosts),
            mode=cfg.security.mode,
        ),
        id_generator=IdGenerator(),
        options=options or {},
    )


def test_module_run_with_all_local_checks(tmp_path: Path) -> None:
    """Exercise SBOM + freshness + postinstall + licenses + container=skipped."""

    # Lockfile so SBOM/freshness/licenses have signal.
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    # Empty node_modules so postinstall has nothing to scan (skipped).
    ctx = _ctx(
        tmp_path,
        options={
            "project_root": tmp_path,
            "enabled_checks": ("sbom", "freshness", "postinstall", "container", "licenses"),
        },
    )
    module = SupplyChainModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    # No image + no scanner → container check downgrades to skipped (info finding).
    findings_by_category = {f.category for f in result.findings}
    assert "supply_chain/container/scanner-not-installed" in findings_by_category
    # SBOM index written.
    sbom_index = json.loads((ctx.run_dir / "sbom" / "index.json").read_text(encoding="utf-8"))
    assert sbom_index["components_count"] == 1
    # Aggregate supply_chain/index.json written too.
    aggregate = json.loads(
        (ctx.run_dir / "supply_chain" / "index.json").read_text(encoding="utf-8")
    )
    assert aggregate["sbom"]["components_count"] == 1


def test_module_emit_metrics_counts_signals(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    ctx = _ctx(
        tmp_path,
        options={
            "project_root": tmp_path,
            "enabled_checks": ("sbom", "freshness"),
        },
    )
    module = SupplyChainModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.metrics.get("components_total") == 1
    assert "duration_ms" in result.metrics


def test_module_skipped_when_no_checks_enabled(tmp_path: Path) -> None:
    # Override all per-check enabled flags to false via config.
    config_body = (
        "policy:\n"
        "  supply_chain:\n"
        "    sbom: { enabled: false }\n"
        "    osv: { enabled: false }\n"
        "    freshness: { enabled: false }\n"
        "    postinstall: { enabled: false }\n"
        "    container: { enabled: false }\n"
        "    licenses: { enabled: false }\n"
    )
    ctx = _ctx(tmp_path, options={"project_root": tmp_path}, config_body=config_body)
    module = SupplyChainModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.status == "skipped"
