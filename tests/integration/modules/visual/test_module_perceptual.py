"""Integration: perceptual SSIM filter (Phase 21.03)."""

from __future__ import annotations

from pathlib import Path

from engine.config.schema import VisualPerceptualConfig

from modules.visual import VisualModule
from modules.visual.baselines import promote_to_baseline, write_index
from tests.unit.modules.visual._fixtures import (
    build_module_context,
    write_solid_png,
)


def _seed(baselines: Path, src: Path) -> None:
    record = promote_to_baseline(
        baselines_dir=baselines,
        viewport="desktop",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [record])


def test_perceptual_filter_suppresses_subpixel_drift(tmp_path: Path) -> None:
    """When SSIM stays above min_similarity, the pixel diff does not fire."""

    baselines = tmp_path / "b"
    current = tmp_path / "c"
    base_src = write_solid_png(tmp_path / "base.png", size=(20, 20), color=(255, 255, 255))
    _seed(baselines, base_src)
    # Single-pixel change keeps SSIM ~ 1.0.
    from PIL import Image

    img = Image.new("RGB", (20, 20), (255, 255, 255))
    img.putpixel((0, 0), (240, 240, 240))  # near-white, very low contrast.
    (current / "desktop").mkdir(parents=True, exist_ok=True)
    img.save(current / "desktop" / "home.png", format="PNG")

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
        visual_overrides={"perceptual": VisualPerceptualConfig(enabled=True, min_similarity=0.99)},
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    # Pixel diff triggers but SSIM remains ~1.0 → finding is suppressed.
    assert findings == ()


def test_perceptual_filter_lets_large_change_through(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"
    base_src = write_solid_png(tmp_path / "base.png", size=(20, 20), color=(255, 255, 255))
    _seed(baselines, base_src)
    write_solid_png(current / "desktop" / "home.png", size=(20, 20), color=(0, 0, 0))

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
        visual_overrides={"perceptual": VisualPerceptualConfig(enabled=True, min_similarity=0.95)},
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert len(findings) == 1
