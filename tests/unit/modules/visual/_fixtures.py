"""Shared image-fixture helpers for visual-module tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from engine.config.loader import load_config
from engine.config.schema import RootConfig, VisualConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from PIL import Image, ImageDraw


def write_solid_png(
    path: Path,
    *,
    size: tuple[int, int] = (40, 30),
    color: tuple[int, int, int] = (255, 255, 255),
) -> Path:
    """Write a solid-colour PNG at ``path`` and return it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
    image.save(path, format="PNG")
    return path


def write_two_tone_png(
    path: Path,
    *,
    size: tuple[int, int] = (40, 30),
    band: tuple[int, int, int, int] = (0, 0, 10, 30),
    background: tuple[int, int, int] = (255, 255, 255),
    band_color: tuple[int, int, int] = (0, 0, 0),
) -> Path:
    """Write a PNG with a coloured rectangle on a solid background."""

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    x, y, w, h = band
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=band_color)
    image.save(path, format="PNG")
    return path


def write_config(root: Path, *, base_url: str = "http://localhost:3000") -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        f"  base_url: {base_url}\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n",
        encoding="utf-8",
    )
    return p


def load_default_config(tmp_path: Path) -> RootConfig:
    config_path = write_config(tmp_path)
    return load_config(config_path)


def build_module_context(
    tmp_path: Path,
    *,
    options: Iterable[tuple[str, object]] | None = None,
    run_id: str = "RUN-AAAAAAAAAAAA",
    visual_overrides: dict[str, object] | None = None,
) -> ModuleContext:
    config = load_default_config(tmp_path)
    if visual_overrides:
        new_visual = config.visual.model_copy(update=visual_overrides)
        config = config.model_copy(update={"visual": new_visual})
    run_dir = tmp_path / ".sentinel" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    opts: dict[str, object] = dict(options or ())
    return ModuleContext(
        module_name="visual",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id=run_id,
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=opts,
    )


__all__ = [
    "VisualConfig",
    "build_module_context",
    "load_default_config",
    "write_config",
    "write_solid_png",
    "write_two_tone_png",
]
