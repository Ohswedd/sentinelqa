"""Integration: VisualModule diff pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from modules.visual import VisualModule
from modules.visual.baselines import promote_to_baseline, write_index
from tests.unit.modules.visual._fixtures import (
    build_module_context,
    write_solid_png,
    write_two_tone_png,
)


def _seed_baseline(
    baselines_dir: Path,
    *,
    viewport: str,
    route_slug: str,
    source: Path,
    run_id: str = "RUN-BASELINEBASE",
) -> None:
    record = promote_to_baseline(
        baselines_dir=baselines_dir,
        viewport=viewport,
        route_slug=route_slug,
        source_png=source,
        captured_by_run_id=run_id,
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines_dir, [record])


def test_identical_capture_yields_match_and_no_finding(tmp_path: Path) -> None:
    baselines = tmp_path / "baselines"
    current = tmp_path / "current"
    src = write_solid_png(tmp_path / "src.png", size=(8, 8), color=(200, 200, 200))
    _seed_baseline(baselines, viewport="mobile", route_slug="home", source=src)
    write_solid_png(current / "mobile" / "home.png", size=(8, 8), color=(200, 200, 200))

    ctx = build_module_context(
        tmp_path,
        options=[("visual", {"baselines_dir": str(baselines), "current_root": str(current)})],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert findings == ()

    index_payload = json.loads((ctx.run_dir / "visual" / "index.json").read_text(encoding="utf-8"))
    assert index_payload["pairs"][0]["status"] == "match"
    assert index_payload["pairs"][0]["baseline_sha256"]


def test_modified_capture_emits_pixel_diff_finding(tmp_path: Path) -> None:
    baselines = tmp_path / "baselines"
    current = tmp_path / "current"
    base_src = write_solid_png(tmp_path / "base.png", size=(40, 30), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="desktop", route_slug="home", source=base_src)
    write_two_tone_png(
        current / "desktop" / "home.png",
        size=(40, 30),
        band=(0, 0, 20, 30),
        background=(255, 255, 255),
        band_color=(0, 0, 0),
    )

    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {
                    "baselines_dir": str(baselines),
                    "current_root": str(current),
                    "threshold": 0.01,
                },
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert len(findings) == 1
    assert findings[0].category == "visual_pixel_diff"

    diff_overlay = ctx.run_dir / "visual" / "diff" / "desktop" / "home.png"
    assert diff_overlay.exists()


def test_size_mismatch_emits_high_severity_finding(tmp_path: Path) -> None:
    baselines = tmp_path / "baselines"
    current = tmp_path / "current"
    base_src = write_solid_png(tmp_path / "base.png", size=(20, 20), color=(0, 0, 0))
    _seed_baseline(baselines, viewport="desktop", route_slug="home", source=base_src)
    write_solid_png(current / "desktop" / "home.png", size=(40, 20), color=(0, 0, 0))

    ctx = build_module_context(
        tmp_path,
        options=[("visual", {"baselines_dir": str(baselines), "current_root": str(current)})],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].category == "visual_size_mismatch"


def test_missing_current_when_baseline_exists(tmp_path: Path) -> None:
    baselines = tmp_path / "baselines"
    src = write_solid_png(tmp_path / "base.png", size=(8, 8), color=(10, 10, 10))
    _seed_baseline(baselines, viewport="mobile", route_slug="home", source=src)

    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {"baselines_dir": str(baselines), "current_root": str(tmp_path / "empty")},
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert len(findings) == 1
    assert findings[0].category == "visual_missing_current"


def test_missing_baseline_does_not_emit_finding(tmp_path: Path) -> None:
    current = tmp_path / "current"
    write_solid_png(current / "mobile" / "home.png", size=(8, 8), color=(255, 0, 0))
    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {"baselines_dir": str(tmp_path / "baselines"), "current_root": str(current)},
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert findings == ()


def test_threshold_override_via_options(tmp_path: Path) -> None:
    baselines = tmp_path / "baselines"
    current = tmp_path / "current"
    src = write_solid_png(tmp_path / "base.png", size=(20, 20), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="desktop", route_slug="home", source=src)
    # One-pixel change → fraction 1/400 = 0.0025.
    (current / "desktop").mkdir(parents=True, exist_ok=True)
    cur_path = current / "desktop" / "home.png"
    img = Image.new("RGB", (20, 20), (255, 255, 255))
    img.putpixel((0, 0), (0, 0, 0))
    img.save(cur_path, format="PNG")

    # With threshold 0.01 (default-ish), 0.0025 is below → no finding.
    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {
                    "baselines_dir": str(baselines),
                    "current_root": str(current),
                    "threshold": 0.01,
                },
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, module.execute(ctx, specs=()))
    assert findings == ()

    # With threshold 0.0001, the single-pixel change crosses.
    ctx2 = build_module_context(
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
    module2 = VisualModule(ctx2.config, ctx2.safety_decision)
    outcome = module2.execute(ctx2, specs=())
    findings2 = module2.emit_findings(ctx2, outcome)
    assert len(findings2) == 1


def test_metrics_count_each_status(tmp_path: Path) -> None:
    baselines = tmp_path / "baselines"
    current = tmp_path / "current"
    matched_src = write_solid_png(tmp_path / "matched.png", size=(8, 8), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="mobile", route_slug="home", source=matched_src)
    write_solid_png(current / "mobile" / "home.png", size=(8, 8), color=(255, 255, 255))
    # New route → missing_baseline.
    write_solid_png(current / "mobile" / "new.png", size=(8, 8), color=(0, 0, 0))

    ctx = build_module_context(
        tmp_path,
        options=[
            (
                "visual",
                {"baselines_dir": str(baselines), "current_root": str(current)},
            )
        ],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    metrics = module.emit_metrics(ctx, outcome)
    assert metrics["pairs_total"] == 2
    assert metrics["pairs_match"] == 1
    assert metrics["pairs_missing_baseline"] == 1
