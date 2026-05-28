"""A module raising mid-run does NOT crash the run."""

from __future__ import annotations

from pathlib import Path

from engine.config.loader import load_config
from engine.errors.base import TestExecutionError
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return p


def test_module_error_captured_not_crashed(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = ModuleRegistry()

    def explode(cfg, decision):
        raise TestExecutionError(detail="explosion in module")

    registry.register_module("functional", explode)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, requested_modules=["functional"])

    # Module crashed → run is `incomplete` (CLAUDE §10 honesty), not `failed`.
    assert test_run.status == "incomplete"
    assert "functional" in test_run.modules_run


def test_module_arbitrary_exception_handled(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = ModuleRegistry()

    def explode(cfg, decision):
        raise RuntimeError("uncategorized")

    registry.register_module("functional", explode)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, requested_modules=["functional"])
    assert test_run.status == "incomplete"


def test_module_error_is_categorized_by_analyzer(tmp_path: Path) -> None:
    """Phase 09 rehome: every module-level exception flows through
    :func:`engine.analyzer.categorize.categorize_module_error` so the
    Reporter / SDK can show *why* a module fell over instead of just
    "errored"."""

    config = load_config(_write_config(tmp_path))
    registry = ModuleRegistry()

    def explode(cfg, decision):
        raise ModuleNotFoundError("missing dependency")

    registry.register_module("functional", explode)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )

    # Capture context to assert on ModuleOutcome fields.
    captured = {}
    original_run_modules = lifecycle.run_modules

    def spy(ctx):
        original_run_modules(ctx)
        captured["outcomes"] = list(ctx.module_outcomes)

    lifecycle.run_modules = spy  # type: ignore[method-assign]
    lifecycle.execute(config, requested_modules=["functional"])

    outcomes = captured["outcomes"]
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.status == "errored"
    assert outcome.error_type == "ModuleNotFoundError"
    assert outcome.error_category == "environment_failure"
    assert outcome.error_confidence is not None and outcome.error_confidence >= 0.85
    assert outcome.error_rationale is not None
    assert "functional" in outcome.error_rationale


def test_module_test_execution_error_categorized_as_test_bug(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = ModuleRegistry()

    def explode(cfg, decision):
        raise TestExecutionError(detail="suite malformed")

    registry.register_module("functional", explode)

    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )

    captured: dict[str, list] = {"outcomes": []}
    original_run_modules = lifecycle.run_modules

    def spy(ctx):
        original_run_modules(ctx)
        captured["outcomes"] = list(ctx.module_outcomes)

    lifecycle.run_modules = spy  # type: ignore[method-assign]
    lifecycle.execute(config, requested_modules=["functional"])

    outcome = captured["outcomes"][0]
    assert outcome.error_category == "test_bug"
    assert outcome.error_type == "TestExecutionError"
