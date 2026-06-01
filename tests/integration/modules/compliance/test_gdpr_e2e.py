"""ComplianceModule end-to-end against synthetic GDPR signals.

The phase README points at the Phase-26 Next.js example as a fixture
that deliberately ships no banner, so the check should fire. We
exercise this by writing a synthetic ``compliance/signals/gdpr.json``
that mirrors what the TS runtime emits.
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
    (signals_root / "gdpr.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def test_nextjs_example_without_banner_fires_finding(tmp_path: Path) -> None:
    """A Next.js style entry route with no banner + analytics cookie fires."""

    signals_root = tmp_path / "signals"
    _write_signals(
        signals_root,
        [
            {
                "route": "/",
                "banner": {"present": False},
                "cookies_on_first_load": [
                    {"name": "_ga", "domain": ".example.test", "essential": False}
                ],
            }
        ],
    )
    options = ComplianceModuleOptions(
        enabled_checks=("gdpr",),
        signals_root=signals_root,
        flag_missing_consent_banner=True,
    )
    ctx = _make_context(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    module.collect_evidence(ctx, outcome)
    findings = module.emit_findings(ctx, outcome)

    categories = {f.category for f in findings}
    assert "compliance.gdpr.cookies-before-consent" in categories
    assert "compliance.gdpr.consent-banner-missing" in categories
    # Persisted summary lands at the documented path.
    summary = json.loads((ctx.run_dir / "compliance" / "gdpr.json").read_text())
    assert summary["pages_checked"] == 1
    assert summary["schema_version"] == "1"


def test_banner_present_only_essential_cookies_clean(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    _write_signals(
        signals_root,
        [
            {
                "route": "/",
                "banner": {"present": True},
                "cookies_on_first_load": [{"name": "sessionid", "essential": True}],
            }
        ],
    )
    options = ComplianceModuleOptions(
        enabled_checks=("gdpr",),
        signals_root=signals_root,
        flag_missing_consent_banner=True,
    )
    ctx = _make_context(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    findings = module.emit_findings(ctx, outcome)
    assert findings == ()


def test_missing_signals_file_keeps_module_silent(tmp_path: Path) -> None:
    options = ComplianceModuleOptions(
        enabled_checks=("gdpr",),
        signals_root=tmp_path / "nonexistent",
    )
    ctx = _make_context(tmp_path, options)
    module = ComplianceModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, ())
    module.collect_evidence(ctx, outcome)
    findings = module.emit_findings(ctx, outcome)
    assert findings == ()
    # the engineering guidelines: no fake completion — the index.json reflects that
    # nothing actually ran.
    index = json.loads((ctx.run_dir / "compliance" / "index.json").read_text())
    assert index["gdpr_ran"] is False
