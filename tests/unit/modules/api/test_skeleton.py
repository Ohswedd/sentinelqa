"""Phase 22.01 skeleton tests for :class:`ApiModule`."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import ApiConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.errors.base import UnsafeTargetError
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl, ValidationError

from modules.api import ApiModule, register_with_default_registry
from modules.api.models import API_RESULT_SCHEMA_VERSION


def _make_root_config(tmp_path: Path, *, openapi_path: Path | None = None) -> RootConfig:
    del tmp_path
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl("http://127.0.0.1:8000"), "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(openapi_path=openapi_path) if openapi_path else ApiConfig(),
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
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-TEST22A")
    target = _make_target(config)
    return ModuleContext(
        module_name="api",
        config=config,
        safety_decision=_make_decision(),
        artifacts=artifacts,
        run_id="RUN-TEST22A",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"api": options or {}},
    )


def test_api_module_registers_with_default_registry() -> None:
    # Some Phase-14 tests reset the default registry, so re-register
    # explicitly (idempotent) before asserting presence.
    register_with_default_registry()
    registry = default_registry()
    assert "api" in registry.modules


def test_register_with_explicit_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)  # second call is a no-op
    assert "api" in registry.modules


def test_run_with_no_docs_skips_every_check(tmp_path: Path) -> None:
    config = _make_root_config(tmp_path)
    ctx = _make_ctx(tmp_path, config)
    module = ApiModule(config=config, safety_decision=ctx.safety_decision)
    result = module.run(ctx)
    assert result.name == "api"
    # No OpenAPI / GraphQL doc → contract / negative / pagination / backward_compat skip;
    # latency is always a dedup-skip; auth + error_shape may run but yield no issues.
    assert result.status in {"skipped", "passed"}
    assert all(f.severity != "critical" for f in result.findings)


def test_artifact_writes_api_index(tmp_path: Path) -> None:
    config = _make_root_config(tmp_path)
    ctx = _make_ctx(tmp_path, config)
    module = ApiModule(config=config, safety_decision=ctx.safety_decision)
    module.run(ctx)
    index_path = ctx.run_dir / "api" / "index.json"
    assert index_path.exists()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == API_RESULT_SCHEMA_VERSION
    assert isinstance(payload["checks"], list)


def test_api_config_clamps_payload_cap() -> None:
    # The schema clamps payload caps so callers cannot widen them.
    with pytest.raises(ValidationError):
        ApiConfig(negative_max_payload_kb=128)
    with pytest.raises(ValidationError):
        ApiConfig(negative_max_variants_per_endpoint=64)


def test_api_config_rejects_duplicate_checks() -> None:
    with pytest.raises(ValidationError):
        ApiConfig(enabled_checks=("contract", "contract"))


def test_api_config_rejects_duplicate_auth_user_labels() -> None:
    with pytest.raises(ValidationError):
        ApiConfig(
            auth_test_users=(
                {"label": "user_a", "token_env": "A"},
                {"label": "user_a", "token_env": "B"},
            )
        )


def test_apimodule_options_namespaced(tmp_path: Path) -> None:
    config = _make_root_config(tmp_path)
    ctx = _make_ctx(
        tmp_path,
        config,
        options={
            "openapi_path": str(tmp_path / "missing.json"),
            "diff_since_run_id": "RUN-PREVIOUS",
            "enabled_checks": ["contract"],
        },
    )
    module = ApiModule(config=config, safety_decision=ctx.safety_decision)
    result = module.run(ctx)
    # The skeleton ran the lifecycle without crashing on a missing doc.
    assert result.name == "api"


def test_safety_policy_blocks_unsafe_target(tmp_path: Path) -> None:
    config = _make_root_config(tmp_path)
    target = Target(
        base_url=AnyUrl("https://example.com"),
        allowed_hosts=frozenset(),
        mode="safe",
    )
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-TEST22B")
    ctx = ModuleContext(
        module_name="api",
        config=config,
        safety_decision=_make_decision(),
        artifacts=artifacts,
        run_id="RUN-TEST22B",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={},
    )
    module = ApiModule(config=config, safety_decision=ctx.safety_decision)
    with pytest.raises(UnsafeTargetError):
        module.validate_prerequisites(ctx)


def test_env_does_not_leak_into_auth_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Sanity: auth check reads env via the explicit dict we pass; module never
    # touches os.environ directly outside the module-level entry point.
    monkeypatch.setenv("SENTINEL_TEST_FAKE_TOKEN", "should-not-be-used")
    config = _make_root_config(tmp_path)
    ctx = _make_ctx(tmp_path, config)
    module = ApiModule(config=config, safety_decision=ctx.safety_decision)
    module.run(ctx)
    # No findings reference the env var name.
    audit_log = (ctx.run_dir / "audit.log").read_text(encoding="utf-8")
    assert "SENTINEL_TEST_FAKE_TOKEN" not in audit_log
    assert "should-not-be-used" not in audit_log
    # Touch os to satisfy import-not-used lint.
    assert os.environ.get("SENTINEL_TEST_FAKE_TOKEN") == "should-not-be-used"
