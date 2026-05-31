"""Phase 34.03 — CCPA module end-to-end against synthetic link-follow data.

The task spec calls for a stub server that links to a 200 privacy
policy *without* an opt-out form. We exercise the module by writing
synthetic ``compliance/signals/ccpa.json`` that mirrors what the
runner would produce after following the link (link_followed=True,
target_has_opt_out_form=False).
"""

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

from modules.compliance.module import ComplianceModule
from modules.compliance.options import ComplianceModuleOptions


def _make_context(tmp_path: Path, options: ComplianceModuleOptions) -> ModuleContext:
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
        reason="e2e_fixture",
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


def _write_signals(signals_root: Path, payload: list[dict]) -> None:
    signals_root.mkdir(parents=True, exist_ok=True)
    (signals_root / "ccpa.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def test_link_targets_privacy_policy_without_opt_out_form(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    _write_signals(
        signals_root,
        [
            {
                "route": "/",
                "link_text": "Do Not Sell or Share My Personal Information",
                "link_href": "/privacy",
                "link_followed": True,
                "target_has_opt_out_form": False,
            }
        ],
    )
    options = ComplianceModuleOptions(
        enabled_checks=("ccpa",),
        signals_root=signals_root,
    )
    ctx = _make_context(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    module.collect_evidence(ctx, outcome)
    findings = module.emit_findings(ctx, outcome)

    categories = {f.category for f in findings}
    assert "compliance.ccpa.do-not-sell-link-opt-out-missing" in categories
    summary = json.loads((ctx.run_dir / "compliance" / "ccpa.json").read_text())
    assert summary["pages_checked"] == 1


def test_missing_link_fires_separate_finding(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    _write_signals(
        signals_root,
        [
            {
                "route": "/account",
                "link_text": "Privacy Policy",
                "link_href": "/policy",
            }
        ],
    )
    options = ComplianceModuleOptions(
        enabled_checks=("ccpa",),
        signals_root=signals_root,
    )
    ctx = _make_context(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    findings = module.emit_findings(ctx, outcome)
    assert any(f.category == "compliance.ccpa.do-not-sell-link-missing" for f in findings)


def test_relaxed_link_presence_only_flags_opt_out_form(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    _write_signals(
        signals_root,
        [
            {"route": "/", "link_text": "", "link_href": ""},
            {
                "route": "/account",
                "link_text": "Do Not Sell",
                "link_href": "/dns",
                "link_followed": True,
                "target_has_opt_out_form": False,
            },
        ],
    )
    options = ComplianceModuleOptions(
        enabled_checks=("ccpa",),
        signals_root=signals_root,
        enforce_ccpa_link_presence=False,
    )
    ctx = _make_context(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    findings = module.emit_findings(ctx, outcome)
    categories = {f.category for f in findings}
    assert "compliance.ccpa.do-not-sell-link-missing" not in categories
    assert "compliance.ccpa.do-not-sell-link-opt-out-missing" in categories
