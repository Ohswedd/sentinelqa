"""Edge cases for the run lifecycle to round out coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.errors.base import ConfigError, SentinelError
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import LifecycleContext, RunLifecycle


def _write_all_modules_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "modules:\n  functional: true\n  api: true\n  accessibility: true\n"
        "  performance: true\n  visual: true\n  security: true\n"
        "  chaos: true\n  llm_audit: true\n",
        encoding="utf-8",
    )
    return p


def test_modules_to_run_covers_every_branch(tmp_path: Path) -> None:
    config = load_config(_write_all_modules_config(tmp_path))
    lc = RunLifecycle(artifacts_root=tmp_path / "runs", registry=ModuleRegistry())
    test_run = lc.execute(config)
    # All enabled modules are visited, all "skipped" because none registered.
    assert set(test_run.modules_run) == {
        "functional",
        "api",
        "accessibility",
        "performance",
        "visual",
        "security",
        "chaos",
        "llm_audit",
    }


def test_load_config_rejects_non_root_config(tmp_path: Path) -> None:
    lc = RunLifecycle(artifacts_root=tmp_path / "runs")
    ctx = LifecycleContext(
        config="not a config",
        registry=ModuleRegistry(),
        requested_modules=None,
        dry_run=False,
        ci=False,
    )
    with pytest.raises(ConfigError):
        lc.load_config(ctx)


def test_validate_config_catches_post_load_mutation(tmp_path: Path) -> None:
    cfg = load_config(_write_all_modules_config(tmp_path))
    lc = RunLifecycle(artifacts_root=tmp_path / "runs")
    ctx = LifecycleContext(
        config=cfg,
        registry=ModuleRegistry(),
        requested_modules=None,
        dry_run=False,
        ci=False,
    )
    # Replace the config with something that fails RootConfig validation.
    bad_cfg = type("Bad", (), {"to_dict": lambda self: {"version": "not-an-int"}})()
    ctx.config = bad_cfg
    with pytest.raises(ConfigError):
        lc.validate_config(ctx)


def test_reporter_emits_findings_and_score_from_typed_ctx(tmp_path: Path) -> None:
    """reporter contract: typed findings on the lifecycle
    context surface in ``findings.json`` / ``score.json`` / ``report.md``.

    now owns score computation; this test asserts the typed
    findings the test attaches drive the reporter via the canonical
    Phase-14 score (recomputed from those findings) rather than a
    hand-set placeholder.
    """

    from datetime import UTC, datetime

    from engine.domain.evidence import Evidence
    from engine.domain.finding import Finding, FindingLocation
    from engine.orchestrator.registry import LifecyclePhase

    cfg = load_config(_write_all_modules_config(tmp_path))
    registry = ModuleRegistry()

    def attach_typed_state(ctx) -> None:
        ctx.typed_findings = (
            Finding(
                id="FND-CTXAAAAAAAAA",
                run_id=ctx.run_id,
                module="security",
                category="security/headers",
                severity="high",
                confidence=0.85,
                title="Session cookie missing Secure flag",
                description="POST /login Set-Cookie header lacks Secure.",
                location=FindingLocation(route="/login"),
                evidence=(
                    Evidence(
                        id="EVD-CTXAAAAAAAAA",
                        type="network_log",
                        path=Path("traces/login.har"),
                        redacted=True,
                    ),
                ),
                recommendation="Set the Secure attribute.",
                affected_target="http://localhost:3000",
                created_at=datetime.now(UTC),
            ),
        )

    registry.register_phase_hook(LifecyclePhase.NORMALIZE_FINDINGS, attach_typed_state)

    lc = RunLifecycle(artifacts_root=tmp_path / "runs", registry=registry)
    tr = lc.execute(cfg)
    run_dir = tmp_path / "runs" / tr.id
    assert (run_dir / "findings.json").exists()
    assert (run_dir / "score.json").exists()
    findings = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["findings"][0]["id"] == "FND-CTXAAAAAAAAA"
    score = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    # derives the score: one high-severity finding in security
    # → security axis = 100-17.5 = 82.5 → total weighted = 96.5.
    assert score["total"] == 96.5
    assert score["release_decision"] == "blocked"
    assert "FND-CTXAAAAAAAAA" in score["blockers"]


def test_module_raises_sentinel_error_subclass(tmp_path: Path) -> None:
    cfg = load_config(_write_all_modules_config(tmp_path))
    registry = ModuleRegistry()

    class CustomError(SentinelError):
        DEFAULT_CODE = "E-RUN-001"

    def explode(c, d):
        raise CustomError(detail="custom")

    registry.register_module("functional", explode)
    lc = RunLifecycle(
        artifacts_root=tmp_path / "runs",
        registry=registry,
    )
    tr = lc.execute(cfg, requested_modules=["functional"])
    assert tr.status == "incomplete"
