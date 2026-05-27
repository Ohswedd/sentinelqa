"""ModuleRegistry behavior."""

from __future__ import annotations

import pytest
from engine.orchestrator.registry import (
    LifecyclePhase,
    ModuleRegistry,
    default_registry,
)


def test_register_and_clear() -> None:
    reg = ModuleRegistry()
    reg.register_module("functional", lambda cfg, d: None)
    assert "functional" in reg.modules
    reg.clear()
    assert reg.modules == {}


def test_double_register_rejected() -> None:
    reg = ModuleRegistry()
    reg.register_module("functional", lambda cfg, d: None)
    with pytest.raises(ValueError):
        reg.register_module("functional", lambda cfg, d: None)


def test_phase_hook_registration() -> None:
    reg = ModuleRegistry()
    captured: list[str] = []
    reg.register_phase_hook(LifecyclePhase.BUILD_EXECUTION_PLAN, lambda ctx: captured.append("a"))
    reg.register_phase_hook(LifecyclePhase.BUILD_EXECUTION_PLAN, lambda ctx: captured.append("b"))
    assert len(reg.phase_hooks[LifecyclePhase.BUILD_EXECUTION_PLAN]) == 2


def test_default_registry_singleton() -> None:
    assert default_registry() is default_registry()
