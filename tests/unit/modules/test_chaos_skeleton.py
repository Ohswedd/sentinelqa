"""Phase 23.01 skeleton tests for :class:`ChaosModule`."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import ChaosConfig, ModulesConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.errors.base import UnsafeTargetError
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl, ValidationError

from modules.chaos import ChaosModule, register_with_default_registry
from modules.chaos.models import CHAOS_RESULT_SCHEMA_VERSION


def _make_root_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl("http://127.0.0.1:8000"), "allowed_hosts": ("127.0.0.1",)},
        modules=ModulesConfig(chaos=True),
        chaos=ChaosConfig(),
    )


def _make_target(config: RootConfig) -> Target:
    return Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )


def _make_decision() -> SafetyDecision:
    return SafetyDecision(
        allowed=True,
        reason="local fixture",
        host="127.0.0.1",
        mode="safe",
        decided_at=datetime.now(UTC),
    )


def _make_ctx(
    tmp_path: Path, config: RootConfig, *, options: dict[str, Any] | None = None
) -> ModuleContext:
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-CHAOS01")
    target = _make_target(config)
    return ModuleContext(
        module_name="chaos",
        config=config,
        safety_decision=_make_decision(),
        artifacts=artifacts,
        run_id="RUN-CHAOS01",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"chaos": options or {}}.get("chaos", {}),
    )


def test_chaos_module_registers_with_default_registry() -> None:
    register_with_default_registry()
    registry = default_registry()
    assert "chaos" in registry.modules


def test_register_with_explicit_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "chaos" in registry.modules


def test_module_off_by_default_in_modules_config() -> None:
    cfg = ModulesConfig()
    assert cfg.chaos is False


def test_chaos_config_rejects_duplicate_categories() -> None:
    with pytest.raises(ValidationError):
        ChaosConfig(enabled_categories=("network", "network"))  # type: ignore[arg-type]


def test_chaos_config_rejects_duplicate_scenarios() -> None:
    with pytest.raises(ValidationError):
        ChaosConfig(enabled_scenarios=("network.api_500", "network.api_500"))


def test_chaos_config_clamps_slow_3g_kbps() -> None:
    # Below floor / above ceiling reject.
    with pytest.raises(ValidationError):
        ChaosConfig(slow_3g_kbps=50)
    with pytest.raises(ValidationError):
        ChaosConfig(slow_3g_kbps=200_000)
    # In-range round-trips.
    assert ChaosConfig(slow_3g_kbps=2_000).slow_3g_kbps == 2_000


def test_run_with_no_events_file_skips_every_category(tmp_path: Path) -> None:
    config = _make_root_config()
    ctx = _make_ctx(tmp_path, config)
    module = ChaosModule(config=config, safety_decision=ctx.safety_decision)
    result = module.run(ctx)
    assert result.name == "chaos"
    # All four categories requested; no events → all four reported as
    # skipped → module status is "skipped".
    assert result.status == "skipped"
    index_path = ctx.run_dir / "chaos" / "index.json"
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == CHAOS_RESULT_SCHEMA_VERSION
    assert {entry["category"] for entry in payload["categories"]} == {
        "network",
        "session",
        "ux",
        "data",
    }
    assert all(entry["skipped"] for entry in payload["categories"])


def test_safety_policy_blocks_unsafe_target(tmp_path: Path) -> None:
    config = _make_root_config()
    target = Target(
        base_url=AnyUrl("https://example.com"),
        allowed_hosts=frozenset(),
        mode="safe",
    )
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-CHAOS02")
    ctx = ModuleContext(
        module_name="chaos",
        config=config,
        safety_decision=_make_decision(),
        artifacts=artifacts,
        run_id="RUN-CHAOS02",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={},
    )
    module = ChaosModule(config=config, safety_decision=ctx.safety_decision)
    with pytest.raises(UnsafeTargetError):
        module.validate_prerequisites(ctx)
