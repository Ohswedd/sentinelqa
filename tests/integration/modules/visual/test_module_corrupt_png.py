"""Integration: corrupt PNG files surface as size_mismatch findings."""

from __future__ import annotations

from pathlib import Path

from modules.visual import VisualModule
from modules.visual.baselines import promote_to_baseline, write_index
from tests.unit.modules.visual._fixtures import (
    build_module_context,
    write_solid_png,
)


def test_corrupt_current_png_emits_size_mismatch(tmp_path: Path) -> None:
    baselines = tmp_path / "b"
    current = tmp_path / "c"
    src = write_solid_png(tmp_path / "src.png", size=(8, 8), color=(0, 0, 0))
    rec = promote_to_baseline(
        baselines_dir=baselines,
        viewport="desktop",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [rec])
    # Write garbage where the PNG is supposed to be.
    (current / "desktop").mkdir(parents=True, exist_ok=True)
    (current / "desktop" / "home.png").write_bytes(b"not a png")

    ctx = build_module_context(
        tmp_path,
        options=[("visual", {"baselines_dir": str(baselines), "current_root": str(current)})],
    )
    module = VisualModule(ctx.config, ctx.safety_decision)
    outcome = module.execute(ctx, specs=())
    findings = module.emit_findings(ctx, outcome)
    assert len(findings) == 1
    assert findings[0].category == "visual_size_mismatch"
