"""Phase 34 — ComplianceModule lifecycle + options + dict-options branches."""

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

from modules.compliance.module import (
    ComplianceModule,
    _factory,
    _resolve_enabled_checks,
    register_with_default_registry,
)
from modules.compliance.options import ComplianceModuleOptions


def _ctx(tmp_path: Path, options: ComplianceModuleOptions | dict) -> ModuleContext:
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="t",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="compliance",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=options,
    )


def test_factory_returns_compliance_module(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, ComplianceModuleOptions())
    module = _factory(ctx.config, ctx.safety_decision)
    assert isinstance(module, ComplianceModule)
    # plan() is always ().
    assert module.plan(ctx) == ()


def test_resolve_enabled_checks_defaults_to_all_when_empty() -> None:
    enabled = _resolve_enabled_checks(ComplianceModuleOptions())
    assert enabled == ("gdpr", "ccpa", "soc2_trail", "wcag22")


def test_resolve_enabled_checks_intersects_with_known() -> None:
    enabled = _resolve_enabled_checks(
        ComplianceModuleOptions(enabled_checks=("gdpr", "unknown", "soc2_trail"))
    )
    assert enabled == ("gdpr", "soc2_trail")


def test_dict_options_are_coerced(tmp_path: Path) -> None:
    """The module accepts plain dicts (CLI / pack DSL path) as ``options``."""

    ctx = _ctx(
        tmp_path,
        {
            "enabled_checks": ["soc2_trail"],
            "expected_modules": ["compliance"],
            "require_llm_events": True,
        },
    )
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    module.execute(ctx, ())
    module.collect_evidence(ctx, _outcome_for(module))
    assert module._enabled == ("soc2_trail",)
    summary_path = ctx.run_dir / "compliance" / "soc2_trail.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert any(gate["gate"] == "trail-llm-events" for gate in summary["gates"])


def test_module_emit_metrics_reports_zero_when_nothing_ran(tmp_path: Path) -> None:
    options = ComplianceModuleOptions(
        enabled_checks=("gdpr",),
        signals_root=tmp_path / "nope",
    )
    ctx = _ctx(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    module.execute(ctx, ())
    metrics = module.emit_metrics(ctx, _outcome_for(module))
    assert metrics["checks_run"] == 0
    assert metrics["gdpr_findings"] == 0
    assert metrics["ccpa_findings"] == 0
    assert metrics["soc2_findings"] == 0
    assert metrics["wcag22_findings"] == 0


def test_module_summarize_status_failed_for_high_severity_finding(tmp_path: Path) -> None:
    """A SOC 2 trail check on a missing log produces a high-severity finding."""

    ctx = _ctx(
        tmp_path,
        ComplianceModuleOptions(
            enabled_checks=("soc2_trail",),
            audit_log_path=tmp_path / "missing.log",
        ),
    )
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    module.collect_evidence(ctx, outcome)
    findings = module.emit_findings(ctx, outcome)
    summary = module.summarize(ctx, outcome, findings, metrics={})
    assert summary.status == "failed"


def test_module_summarize_status_skipped_when_nothing_ran(tmp_path: Path) -> None:
    ctx = _ctx(
        tmp_path,
        ComplianceModuleOptions(
            enabled_checks=("gdpr",),
            signals_root=tmp_path / "nope",
        ),
    )
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    module.collect_evidence(ctx, outcome)
    findings = module.emit_findings(ctx, outcome)
    summary = module.summarize(ctx, outcome, findings, metrics={})
    assert summary.status == "skipped"


def test_register_with_default_registry_is_idempotent() -> None:
    from engine.orchestrator.registry import ModuleRegistry

    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "compliance" in registry.modules


def test_validate_prerequisites_enforces_safety_policy(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, ComplianceModuleOptions())
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    # Local target → policy allow; no exception raised.
    module.validate_prerequisites(ctx)


def _outcome_for(module: ComplianceModule):
    from modules.compliance.module import _synthetic_runner_outcome

    return _synthetic_runner_outcome(_dummy_ctx(module), module)


def _dummy_ctx(module: ComplianceModule) -> ModuleContext:
    """Build a minimal ctx for synthesizing a RunnerOutcome in tests."""

    from engine.domain.target import Target

    cfg = module._config
    target = Target(base_url=cfg.target.base_url, mode="safe")
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="t",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="compliance",
        config=cfg,
        safety_decision=safety,
        artifacts=ArtifactDirectory(Path(".")),
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=Path("."),
        target=target,
        id_generator=IdGenerator(),
        options={},
    )
