"""End-to-end scoring via the orchestrator (task 14.04)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from engine.orchestrator.registry import LifecyclePhase, default_registry
from engine.orchestrator.run_lifecycle import RunLifecycle

from tests.unit.scoring.conftest import make_finding, make_module_result


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


def test_clean_run_scores_100_and_passes(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    default_registry().clear()
    try:
        lifecycle = RunLifecycle(artifacts_root=tmp_path / ".sentinel" / "runs")
        test_run = lifecycle.execute(config)
    finally:
        default_registry().clear()

    ctx = lifecycle.last_context
    assert ctx is not None
    assert ctx.typed_score is not None
    assert ctx.typed_score.total == 100.0
    assert ctx.typed_policy is not None
    assert ctx.typed_policy.release_decision == "pass"
    assert test_run.status == "passed"


def test_findings_lower_score_and_drive_decision(tmp_path: Path) -> None:
    """Inject typed findings via a NORMALIZE_FINDINGS hook and verify
    the score / decision the orchestrator computes downstream."""

    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    def inject_findings(ctx) -> None:  # type: ignore[no-untyped-def]
        ctx.typed_findings = (
            make_finding(
                id="FND-INTEGAAA0001",
                module="security",
                severity="high",
                run_id=ctx.run_id,
            ),
        )
        ctx.typed_module_results = (make_module_result(id="MOD-INTEGAAA0001", name="security"),)

    registry.register_phase_hook(LifecyclePhase.NORMALIZE_FINDINGS, inject_findings)
    try:
        lifecycle = RunLifecycle(artifacts_root=tmp_path / ".sentinel" / "runs")
        test_run = lifecycle.execute(config)
    finally:
        registry.clear()

    ctx = lifecycle.last_context
    assert ctx is not None
    assert ctx.typed_score is not None
    assert ctx.typed_policy is not None
    # High security finding triggers `security_high` blocker → blocked.
    assert ctx.typed_policy.release_decision == "blocked"
    assert "FND-INTEGAAA0001" in ctx.typed_policy.blocked_by
    # Lifecycle finalizer translates blocked → failed.
    assert test_run.status == "failed"


def test_score_json_persisted_with_lifecycle_decision(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    def inject(ctx) -> None:  # type: ignore[no-untyped-def]
        ctx.typed_findings = (
            make_finding(
                id="FND-MEDIUMAAAAA1",
                module="accessibility",
                severity="medium",
                run_id=ctx.run_id,
            ),
        )

    registry.register_phase_hook(LifecyclePhase.NORMALIZE_FINDINGS, inject)
    try:
        lifecycle = RunLifecycle(artifacts_root=tmp_path / ".sentinel" / "runs")
        test_run = lifecycle.execute(config)
    finally:
        registry.clear()

    run_dir = tmp_path / ".sentinel" / "runs" / test_run.id
    score_path = run_dir / "score.json"
    assert score_path.exists(), "score.json should be written by the reporter"
    payload = json.loads(score_path.read_text(encoding="utf-8"))
    assert payload["release_decision"] == "pass_with_warnings"
    assert payload["blockers"] == []
    # Components map carries all 8 axes (per the score writer).
    assert set(payload["components"]) == {
        "functional",
        "security",
        "performance",
        "accessibility",
        "api",
        "visual",
        "llm_audit",
        "flake_risk",
    }


def test_unsafe_target_skips_scoring(tmp_path: Path) -> None:
    """When safety blocks the run, scoring hooks never fire."""

    cfg_path = tmp_path / "sentinel.config.yaml"
    cfg_path.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: https://example.com\n  allowed_hosts: []\n"
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    config = load_config(cfg_path)
    default_registry().clear()
    try:
        lifecycle = RunLifecycle(artifacts_root=tmp_path / ".sentinel" / "runs")
        test_run = lifecycle.execute(config)
    finally:
        default_registry().clear()

    assert test_run.status == "unsafe_blocked"
    # Safety short-circuit returns before scoring hooks run; no score
    # is attached to the context.
    ctx = lifecycle.last_context
    assert ctx is not None
    assert ctx.typed_score is None
    assert ctx.typed_policy is None
