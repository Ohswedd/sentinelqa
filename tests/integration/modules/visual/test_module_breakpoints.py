"""Integration: per-viewport baseline + diff."""

from __future__ import annotations

from pathlib import Path

from modules.visual import VisualModule
from modules.visual.baselines import promote_to_baseline, write_index
from tests.unit.modules.visual._fixtures import (
    build_module_context,
    write_solid_png,
)


def test_module_runs_each_viewport_independently(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"
    for vp in ("mobile", "desktop"):
        src = write_solid_png(tmp_path / f"{vp}.png", size=(8, 8), color=(200, 200, 200))
        rec = promote_to_baseline(
            baselines_dir=baselines,
            viewport=vp,
            route_slug="home",
            source_png=src,
            captured_by_run_id="RUN-BASEXXXXXXXX",
            captured_at="2026-05-29T00:00:00+00:00",
        )
        write_index(baselines, [rec])
    # Re-seed final write_index with both records present.
    rec_mobile = promote_to_baseline(
        baselines_dir=baselines,
        viewport="mobile",
        route_slug="home",
        source_png=tmp_path / "mobile.png",
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    rec_desktop = promote_to_baseline(
        baselines_dir=baselines,
        viewport="desktop",
        route_slug="home",
        source_png=tmp_path / "desktop.png",
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [rec_mobile, rec_desktop])

    write_solid_png(current / "mobile" / "home.png", size=(8, 8), color=(200, 200, 200))
    write_solid_png(current / "desktop" / "home.png", size=(8, 8), color=(0, 0, 0))

    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {
                    "baselines_dir": str(baselines),
                    "current_root": str(current),
                    "threshold": 0.0001,
                },
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    # Mobile matches; desktop differs → exactly one finding tied to desktop.
    assert len(findings) == 1
    assert "desktop" in findings[0].title


def test_viewport_subset_skips_others(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"
    src = write_solid_png(tmp_path / "src.png", size=(4, 4), color=(0, 0, 0))
    rec_m = promote_to_baseline(
        baselines_dir=baselines,
        viewport="mobile",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    rec_d = promote_to_baseline(
        baselines_dir=baselines,
        viewport="desktop",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [rec_m, rec_d])
    # Only capture mobile.
    write_solid_png(current / "mobile" / "home.png", size=(4, 4), color=(0, 0, 0))

    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {
                    "baselines_dir": str(baselines),
                    "current_root": str(current),
                    "viewports": ("mobile",),
                },
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    metrics = module.emit_metrics(ctx, outcome)
    assert metrics["pairs_total"] == 1
    assert metrics["pairs_match"] == 1
