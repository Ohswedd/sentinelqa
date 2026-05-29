"""Unit tests for :mod:`modules.visual` skeleton (Phase 21.01)."""

from __future__ import annotations

from pathlib import Path

from engine.modules.base import SentinelModule
from engine.orchestrator.registry import ModuleRegistry

from modules.visual import VisualModule, register_with_default_registry
from modules.visual.module import _factory
from tests.unit.modules.visual._fixtures import build_module_context


def test_visual_is_sentinel_subclass() -> None:
    assert issubclass(VisualModule, SentinelModule)
    assert VisualModule.name == "visual"


def test_register_with_default_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "visual" in registry.modules
    assert registry.modules["visual"] is _factory


def test_factory_returns_module(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path)
    instance = _factory(ctx.config, ctx.safety_decision)
    assert isinstance(instance, VisualModule)


def test_execute_with_no_inputs_returns_skipped(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path)
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    assert outcome.module_result.status == "skipped"


def test_plan_returns_empty(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path)
    module = VisualModule(ctx.config, ctx.safety_decision)
    assert tuple(module.plan(ctx)) == ()


def test_validate_prerequisites_is_noop(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path)
    module = VisualModule(ctx.config, ctx.safety_decision)
    module.validate_prerequisites(ctx)  # does not raise
