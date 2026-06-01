"""Unit tests for :mod:`modules.llm_audit`."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry
from engine.policy.safety import SafetyDecision

from modules.llm_audit import (
    LlmAuditModule,
    LlmAuditModuleOptions,
    register_with_default_registry,
)
from modules.llm_audit.module import ALL_CHECKS, _enabled_checks, _factory


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n",
        encoding="utf-8",
    )
    return p


def _build_ctx(
    tmp_path: Path,
    *,
    options: Mapping[str, Any] | None = None,
) -> ModuleContext:
    config_path = _write_config(tmp_path)
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
        options=dict(options or {}),
    )


def test_module_is_sentinel_subclass() -> None:
    assert issubclass(LlmAuditModule, SentinelModule)
    assert LlmAuditModule.name == "llm_audit"


def test_register_with_default_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "llm_audit" in registry.modules
    assert registry.modules["llm_audit"] is _factory


def test_enabled_checks_defaults_to_all() -> None:
    assert _enabled_checks(()) == frozenset(ALL_CHECKS)


def test_enabled_checks_subset() -> None:
    subset = _enabled_checks(("dead_buttons", "mock_data"))
    assert subset == frozenset({"dead_buttons", "mock_data"})


def test_enabled_checks_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown LLM-audit check"):
        _enabled_checks(("dead_buttons", "not_a_check"))


def test_execute_with_no_signals_returns_skipped(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = LlmAuditModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    assert outcome.module_result.status == "skipped"
    # Index is still persisted so the audit trail is complete.
    index_path = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA" / "llm_audit" / "index.json"
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert {entry["name"] for entry in payload["checks"]} == set(ALL_CHECKS)


def test_options_round_trip_from_mapping(tmp_path: Path) -> None:
    raw = {
        "discovery_path": str(tmp_path / "discovery.json"),
        "signals_root": str(tmp_path / "signals"),
        "checks": "dead_buttons,mock_data",
        "third_party_console_hosts": "google-analytics.com,ads.example.com",
    }
    ctx = _build_ctx(tmp_path, options={"llm_audit": raw})
    from modules.llm_audit.module import _read_options

    opts = _read_options(ctx)
    assert isinstance(opts, LlmAuditModuleOptions)
    assert opts.checks == ("dead_buttons", "mock_data")
    assert opts.third_party_console_hosts == (
        "google-analytics.com",
        "ads.example.com",
    )
    assert opts.discovery_path == Path(raw["discovery_path"])
    assert opts.signals_root == Path(raw["signals_root"])


def test_execute_with_signals_records_findings(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    signals_root.mkdir()
    signals = {
        "rendered_text": [
            {
                "route_url": "http://localhost:3000/dashboard",
                "text": "Coming soon — check back later!",
                "is_authenticated_flow": True,
                "priority": "p0",
            },
        ],
        "buttons": [
            {
                "route_url": "http://localhost:3000/dashboard",
                "selector": "[data-test=dead]",
                "label": "Save",
                "has_static_handler": False,
                "observed_network_within_2s": False,
                "observed_navigation": False,
                "observed_console_error": False,
                "observed_dom_change": False,
            },
        ],
    }
    (signals_root / "signals.json").write_text(json.dumps(signals), encoding="utf-8")
    ctx = _build_ctx(
        tmp_path,
        options={
            "llm_audit": {
                "signals_root": str(signals_root),
                "checks": "coming_soon,dead_buttons",
            }
        },
    )
    module = LlmAuditModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    rule_ids = {f.category for f in findings}
    assert "llm_audit_placeholder_text" in rule_ids
    assert "llm_audit_dead_button" in rule_ids
    # Metrics should report `checks_run = 2` and a positive finding total.
    metrics = module.emit_metrics(ctx, outcome)
    assert metrics["checks_run"] == 2
    assert metrics["findings_total"] >= 2
    summary = module.summarize(ctx, outcome, findings, metrics)
    assert summary.status in {"failed", "passed"}


def test_factory_returns_module(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    instance = _factory(ctx.config, ctx.safety_decision)
    assert isinstance(instance, LlmAuditModule)
