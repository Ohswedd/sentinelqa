"""Shared fixtures for MCP integration tests.

Each test gets an isolated project directory with a minimal valid
``sentinel.config.yaml`` plus a stub registration of the functional
module on the process-wide :class:`engine.orchestrator.registry.ModuleRegistry`
so audits finish without spawning Playwright. The fixture is identical
in spirit to ``tests/integration/sdk/test_audit_against_fixture.py``.

The package-scoped ``_force_gc`` fixture forces a ``gc.collect()`` after
each MCP test runs. Each ``Sentinel.audit`` call internally spins up a
private ``asyncio.run(...)`` loop (the SDK wraps sync methods around the
async ones), and Python's selectors hold a kqueue fd until the loop
object is GC'd. Without an explicit collect, the next test in the suite
can trip ``ResourceWarning: unclosed socket`` through pytest's
``unraisableexception`` plugin.
"""

from __future__ import annotations

import gc
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from engine.orchestrator.registry import ModuleRegistry, default_registry

from sentinelqa import Sentinel
from sentinelqa_mcp.server import MCPServer
from sentinelqa_mcp.tools import SentinelToolset, ToolContext


@pytest.fixture(autouse=True)
def _force_gc() -> Iterator[None]:
    yield
    gc.collect()


def write_minimal_config(root: Path, *, base_url: str = "http://localhost:3000") -> Path:
    cfg = root / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\n"
        "project:\n"
        "  name: mcp-fixture\n"
        "target:\n"
        f"  base_url: {base_url}\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n",
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def stub_functional_registry() -> Iterator[ModuleRegistry]:
    """Register a no-op functional factory on the process-wide registry."""

    reg = default_registry()
    prior: Any = reg.modules.pop("functional", None)
    reg.register_module("functional", lambda cfg, decision: {"ok": True})
    try:
        yield reg
    finally:
        reg.modules.pop("functional", None)
        if prior is not None:
            reg.register_module("functional", prior)


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    write_minimal_config(tmp_path)
    return tmp_path


@pytest.fixture
def sentinel_sdk(project_path: Path) -> Sentinel:
    return Sentinel(project_path=project_path, machine_readable=True)


@pytest.fixture
def server(sentinel_sdk: Sentinel, project_path: Path) -> MCPServer:
    toolset = SentinelToolset.with_defaults()
    return MCPServer(
        toolset=toolset,
        context=ToolContext(sentinel=sentinel_sdk, project_path=project_path),
    )


__all__ = [
    "project_path",
    "sentinel_sdk",
    "server",
    "stub_functional_registry",
    "write_minimal_config",
]
