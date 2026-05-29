"""Shared fixtures for Phase 23 chaos integration tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import ChaosConfig, ModulesConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl

from modules.chaos import ChaosModule


def _root_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl("http://127.0.0.1:8000"), "allowed_hosts": ("127.0.0.1",)},
        modules=ModulesConfig(chaos=True),
        chaos=ChaosConfig(),
    )


def _safety_decision() -> SafetyDecision:
    return SafetyDecision(
        allowed=True,
        reason="local fixture",
        host="127.0.0.1",
        mode="safe",
        decided_at=datetime.now(UTC),
    )


@pytest.fixture()
def chaos_context(tmp_path: Path) -> ModuleContext:
    """Build a :class:`ModuleContext` rooted at ``tmp_path``."""

    config = _root_config()
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-CHAOSITABCDE")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    return ModuleContext(
        module_name="chaos",
        config=config,
        safety_decision=_safety_decision(),
        artifacts=artifacts,
        run_id="RUN-CHAOSITABCDE",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={},
    )


@pytest.fixture()
def make_chaos_module() -> Any:
    """Return a builder so tests pick the config they need."""

    def _builder(ctx: ModuleContext) -> ChaosModule:
        return ChaosModule(config=ctx.config, safety_decision=ctx.safety_decision)

    return _builder


@pytest.fixture()
def write_events_file() -> Any:
    """Write JSONL chaos events into ``<chaos_dir>/events.jsonl``."""

    def _writer(run_dir: Path, events: list[dict[str, Any]]) -> Path:
        chaos_dir = run_dir / "chaos"
        chaos_dir.mkdir(parents=True, exist_ok=True)
        path = chaos_dir / "events.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event) + "\n")
        return path

    return _writer
