"""End-to-end sweep against the broken fixture (task 19.15).

Drives :class:`LlmAuditModule` against ``tests/fixtures/llm_audit_broken/``
and asserts that at least 11 of the 13 our product spec9 checks fire — i.e.
≥ 80% of the catalogue is exercised by the canonical defect catalogue.

The fixture mirrors the HTML examples under
``packages/ts-runtime/fixtures/sample-app-llm-broken/`` but pre-bakes
the runtime signals so the test stays hermetic (no browser, no
network).
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

from modules.llm_audit import LlmAuditModule

FIXTURE_ROOT = Path(__file__).parent.parent.parent.parent / "fixtures" / "llm_audit_broken"


def _build_ctx(tmp_path: Path) -> ModuleContext:
    config_path = tmp_path / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    artifacts_root = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(artifacts_root)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="llm_audit",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=artifacts_root,
        target=target,
        id_generator=IdGenerator(),
        options={
            "llm_audit": {
                "discovery_path": str(FIXTURE_ROOT / "discovery.json"),
                "signals_root": str(FIXTURE_ROOT),
            }
        },
    )


def test_broken_fixture_triggers_at_least_eighty_percent_of_checks(
    tmp_path: Path,
) -> None:
    ctx = _build_ctx(tmp_path)
    module = LlmAuditModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    categories = {f.category for f in findings}
    # Expected categories on this fixture (12 of 13 checks — fake_routes is
    # the lone exception because the broken fixture's only "fake link"
    # points at /feature-x which the discovery treats as observed=404,
    # which DOES trigger fake_routes; we expect everything else too).
    expected = {
        "llm_audit_dead_button",
        "llm_audit_fake_route",
        "llm_audit_fake_endpoint",
        "llm_audit_mock_data",
        "llm_audit_form_no_submit",
        "llm_audit_incomplete_crud",
        "llm_audit_ui_only_auth",
        "llm_audit_hardcoded_cred",
        "llm_audit_client_secret_storage",
        "llm_audit_no_loading_state",
        "llm_audit_no_error_state",
        "llm_audit_validation_mismatch",
        "llm_audit_placeholder_text",
        "llm_audit_console_error",
    }
    matched = expected & categories
    # 13 our product spec9 checks → require ≥ 11 (≥ 80 %). We actually expect 14
    # distinct rule categories because mock_data + placeholder_text + no
    # _loading/no_error each can produce different categories.
    assert len(matched) >= 11, (
        f"Broken-fixture sweep only triggered {len(matched)} categories: "
        f"{sorted(matched)}; expected at least 11."
    )


def test_broken_fixture_persists_index_with_all_checks_enabled(
    tmp_path: Path,
) -> None:
    ctx = _build_ctx(tmp_path)
    module = LlmAuditModule(ctx.config, ctx.safety_decision)
    module.execute(ctx, specs=())
    index_path = ctx.run_dir / "llm_audit" / "index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    enabled = {entry["name"] for entry in payload["checks"]}
    # Every our product spec9 check should be enabled when the CLI is not given
    # an explicit --checks subset.
    from modules.llm_audit.module import ALL_CHECKS

    assert enabled == set(ALL_CHECKS)


def test_broken_fixture_findings_all_have_evidence(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = LlmAuditModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert findings
    for f in findings:
        # our product spec: every finding must carry evidence (at minimum the
        # llm_audit/index.json fallback).
        assert f.evidence, f"finding {f.id} has no evidence"


def test_broken_fixture_credential_redacted_in_findings(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = LlmAuditModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    cred_findings = [f for f in findings if f.category == "llm_audit_hardcoded_cred"]
    assert cred_findings, "expected at least one hardcoded-cred finding"
    blob = "\n".join(f.description for f in cred_findings)
    # The fixture's password ("SuperSecret42") must never leak.
    assert "SuperSecret42" not in blob
    assert "REDACTED" in blob
