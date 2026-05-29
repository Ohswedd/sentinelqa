"""Integration: rect-mask suppresses dynamic-content noise (Phase 21.04)."""

from __future__ import annotations

from pathlib import Path

from engine.config.schema import VisualMaskConfig
from PIL import Image

from modules.visual import VisualModule
from modules.visual.baselines import promote_to_baseline, write_index
from tests.unit.modules.visual._fixtures import build_module_context


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


def test_rect_mask_stabilises_diff_for_dynamic_region(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"

    base = Image.new("RGB", (20, 20), (255, 255, 255))
    base_path = tmp_path / "base.png"
    base.save(base_path, format="PNG")
    _seed(baselines, base_path)

    # Current capture differs only in the (2,2)-(6,6) region — the "clock".
    cur = Image.new("RGB", (20, 20), (255, 255, 255))
    for x in range(2, 6):
        for y in range(2, 6):
            cur.putpixel((x, y), (0, 0, 0))
    (current / "desktop").mkdir(parents=True, exist_ok=True)
    cur.save(current / "desktop" / "home.png", format="PNG")

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
        visual_overrides={
            "masks": (VisualMaskConfig(route="home", rect=(2, 2, 4, 4), reason="clock"),)
        },
    )

    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert findings == (), "Mask covering the dynamic region should suppress the diff"
