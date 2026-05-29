"""Integration: VisualModule.summarize covers skipped/passed/failed branches."""

from __future__ import annotations

from pathlib import Path

from modules.visual import VisualModule
from modules.visual.baselines import promote_to_baseline, write_index
from tests.unit.modules.visual._fixtures import (
    build_module_context,
    write_solid_png,
)


def test_summarize_skipped_when_no_pairs(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path)
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    metrics = module.emit_metrics(ctx, outcome)
    result = module.summarize(ctx, outcome, findings, metrics)
    assert result.status == "skipped"


def test_summarize_passed_when_match_only(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"
    src = write_solid_png(tmp_path / "src.png", size=(4, 4), color=(0, 0, 0))
    rec = promote_to_baseline(
        baselines_dir=baselines,
        viewport="mobile",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [rec])
    write_solid_png(current / "mobile" / "home.png", size=(4, 4), color=(0, 0, 0))

    ctx = build_module_context(
        tmp_path,
        options=[("visual", {"baselines_dir": str(baselines), "current_root": str(current)})],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    metrics = module.emit_metrics(ctx, outcome)
    result = module.summarize(ctx, outcome, findings, metrics)
    assert result.status == "passed"


def test_summarize_failed_when_high_severity_finding(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"
    src = write_solid_png(tmp_path / "src.png", size=(4, 4), color=(0, 0, 0))
    rec = promote_to_baseline(
        baselines_dir=baselines,
        viewport="desktop",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [rec])
    # Mismatched size → size_mismatch → high severity.
    write_solid_png(current / "desktop" / "home.png", size=(8, 8), color=(0, 0, 0))

    ctx = build_module_context(
        tmp_path,
        options=[("visual", {"baselines_dir": str(baselines), "current_root": str(current)})],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    metrics = module.emit_metrics(ctx, outcome)
    result = module.summarize(ctx, outcome, findings, metrics)
    assert result.status == "failed"
