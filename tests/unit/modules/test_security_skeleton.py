"""Tests for the SecurityModule skeleton."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry
from engine.policy.safety import SafetyDecision

from modules.security import SecurityModule, register_with_default_registry
from modules.security.module import (
    _factory,
    _resolve_enabled_checks,
    _resolve_routes,
)
from modules.security.options import SecurityModuleOptions


def _write_config(
    root: Path,
    *,
    base_url: str = "http://localhost:8088",
    security_block: str = "",
) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n  allowed_hosts: [localhost, 127.0.0.1]\n"
        + security_block,
        encoding="utf-8",
    )
    return p


def _build_ctx(
    tmp_path: Path,
    *,
    options: dict[str, Any] | None = None,
    security_block: str = "",
) -> ModuleContext:
    cfg_path = _write_config(tmp_path, security_block=security_block)
    config = load_config(cfg_path)
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="security",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def test_security_module_inherits_sentinel_module() -> None:
    assert issubclass(SecurityModule, SentinelModule)
    assert SecurityModule.name == "security"


def test_factory_returns_security_module(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path))
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="t",
        decided_at=datetime.now(UTC),
    )
    instance = _factory(cfg, safety)
    assert isinstance(instance, SecurityModule)


def test_register_with_default_registry_is_idempotent() -> None:
    reg = ModuleRegistry()
    register_with_default_registry(reg)
    register_with_default_registry(reg)
    assert "security" in reg.modules


def test_resolve_routes_priority(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path))
    # CLI routes win first
    routes = _resolve_routes(cfg, SecurityModuleOptions(routes=("/a",)))
    assert routes == ("/a",)
    # Then discovery, then config, then empty
    no_routes = _resolve_routes(cfg, SecurityModuleOptions())
    assert no_routes == ()


def test_resolve_enabled_checks_respects_config(tmp_path: Path) -> None:
    block = (
        "security:\n"
        "  checks:\n"
        "    headers: false\n"
        "    cookies: true\n"
        "    cors: false\n"
        "    csrf: false\n"
        "    xss_reflected: false\n"
        "    idor: false\n"
        "    frontend_secrets: false\n"
        "    dependency_scan: false\n"
    )
    cfg = load_config(_write_config(tmp_path, security_block=block))
    enabled = _resolve_enabled_checks(cfg, SecurityModuleOptions())
    assert enabled == ("cookies",)


def test_resolve_enabled_checks_cli_restricts(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path))
    enabled = _resolve_enabled_checks(
        cfg, SecurityModuleOptions(enabled_checks=("headers", "cookies"))
    )
    assert enabled == ("headers", "cookies")


def test_skipped_when_no_routes(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.status == "skipped"


def test_safety_policy_enforced_on_validate(tmp_path: Path, monkeypatch) -> None:
    """``validate_prerequisites`` must call ``SafetyPolicy.enforce``."""

    calls: list[Any] = []

    from engine.policy import safety as safety_mod

    original = safety_mod.SafetyPolicy.enforce

    def spy(self, target, mode=None, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((target, mode))
        return original(self, target, mode, **kwargs)

    monkeypatch.setattr(safety_mod.SafetyPolicy, "enforce", spy)
    ctx = _build_ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    module.validate_prerequisites(ctx)
    assert calls
