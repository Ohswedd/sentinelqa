"""Exercise the per-phase hook registry (task 02.04)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.config.loader import load_config
from engine.orchestrator.registry import LifecyclePhase, default_registry
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


def test_every_phase_hook_runs(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    visited: list[str] = []
    for phase in (
        LifecyclePhase.DISCOVER_APP,
        LifecyclePhase.BUILD_EXECUTION_PLAN,
        LifecyclePhase.COLLECT_EVIDENCE,
        LifecyclePhase.NORMALIZE_FINDINGS,
        LifecyclePhase.CALCULATE_QUALITY_SCORE,
        LifecyclePhase.APPLY_QUALITY_GATES,
        LifecyclePhase.GENERATE_REPORTS,
    ):
        # Closure-capture each phase name into the recorded list.
        def make(p: LifecyclePhase) -> Callable[[Any], None]:
            return lambda ctx: visited.append(p.value)

        registry.register_phase_hook(phase, make(phase))

    try:
        lc = RunLifecycle(artifacts_root=tmp_path / ".sentinel" / "runs")
        lc.execute(config)
    finally:
        registry.clear()

    for expected in (
        "discover_app",
        "build_execution_plan",
        "collect_evidence",
        "normalize_findings",
        "calculate_quality_score",
        "apply_quality_gates",
        "generate_reports",
    ):
        assert expected in visited, f"hook for {expected} not invoked"
