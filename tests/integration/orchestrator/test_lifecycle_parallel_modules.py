# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Parallel module execution path (v1.2.0)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from engine.cache import CacheStore
from engine.config.loader import load_config
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle


def _write_config(root: Path, *, modules: tuple[str, ...]) -> Path:
    body = (
        "version: 1\n"
        "project:\n"
        "  name: test-app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
    )
    all_flags = (
        "functional",
        "api",
        "accessibility",
        "performance",
        "visual",
        "security",
        "chaos",
        "llm_audit",
    )
    for flag in all_flags:
        body += f"  {flag}: {'true' if flag in modules else 'false'}\n"
    path = root / "sentinel.config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _make_lifecycle(tmp_path: Path, modules: tuple[str, ...]) -> RunLifecycle:
    _write_config(tmp_path, modules=modules)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    cache = CacheStore(tmp_path / ".sentinel" / "cache")
    registry = ModuleRegistry()
    return RunLifecycle(
        artifacts_root=artifacts_root,
        registry=registry,
        project_root=tmp_path,
        cache_store=cache,
    )


def test_parallel_modules_preserve_input_order(tmp_path: Path) -> None:
    """Outcomes must come back in the order the modules were submitted."""

    lifecycle = _make_lifecycle(
        tmp_path,
        modules=("functional", "accessibility", "performance", "api"),
    )

    finished_log: list[str] = []
    log_lock = threading.Lock()

    def _factory(name: str):
        def _impl(cfg, decision):
            sleep_map = {
                "functional": 0.06,
                "accessibility": 0.02,
                "performance": 0.04,
                "api": 0.01,
            }
            time.sleep(sleep_map[name])
            with log_lock:
                finished_log.append(name)
            return {"ok": True, "name": name}

        return _impl

    for name in ("functional", "accessibility", "performance", "api"):
        lifecycle._registry.register_module(name, _factory(name))

    config = load_config(tmp_path / "sentinel.config.yaml")
    test_run = lifecycle.execute(config, module_concurrency=4)

    assert set(test_run.modules_run) == {
        "functional",
        "accessibility",
        "performance",
        "api",
    }
    outcome_names = [o.name for o in lifecycle._last_context.module_outcomes]
    # Lifecycle iterates in its own canonical order (functional, api,
    # accessibility, performance, ...). Outcomes must follow that.
    assert outcome_names == ["functional", "api", "accessibility", "performance"]
    # Different finish order proves concurrency actually happened.
    assert finished_log != outcome_names


def test_parallel_module_failure_does_not_block_siblings(tmp_path: Path) -> None:
    """A raising module must not prevent its siblings from finishing."""

    lifecycle = _make_lifecycle(tmp_path, modules=("functional", "api"))

    def _ok(cfg, decision):
        return {"ok": True}

    def _raises(cfg, decision):
        raise RuntimeError("module exploded")

    lifecycle._registry.register_module("functional", _raises)
    lifecycle._registry.register_module("api", _ok)

    config = load_config(tmp_path / "sentinel.config.yaml")
    test_run = lifecycle.execute(config, module_concurrency=4)

    statuses = {o.name: o.status for o in lifecycle._last_context.module_outcomes}
    assert statuses["functional"] == "errored"
    assert statuses["api"] == "succeeded"
    # Run finishes; status reflects the error (incomplete since a module errored).
    assert test_run.status in {"incomplete", "failed"}


def test_concurrency_one_matches_sequential_behaviour(tmp_path: Path) -> None:
    """``module_concurrency=1`` must be byte-equivalent to the sequential path."""

    lifecycle = _make_lifecycle(tmp_path, modules=("functional", "api"))

    def _ok(name: str):
        def _impl(cfg, decision):
            return {"name": name}

        return _impl

    lifecycle._registry.register_module("functional", _ok("functional"))
    lifecycle._registry.register_module("api", _ok("api"))

    config = load_config(tmp_path / "sentinel.config.yaml")
    test_run = lifecycle.execute(config, module_concurrency=1)
    statuses = {o.name: o.status for o in lifecycle._last_context.module_outcomes}
    assert statuses == {"functional": "succeeded", "api": "succeeded"}
    assert test_run.status == "passed"


def test_concurrency_clamped_to_module_count(tmp_path: Path) -> None:
    """Requesting more workers than modules does not break the run."""

    lifecycle = _make_lifecycle(tmp_path, modules=("functional",))
    lifecycle._registry.register_module("functional", lambda cfg, decision: {"ok": True})
    config = load_config(tmp_path / "sentinel.config.yaml")
    test_run = lifecycle.execute(config, module_concurrency=16)
    assert test_run.status == "passed"
