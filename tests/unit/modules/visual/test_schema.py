"""Unit tests for the visual config schema extensions (Phase 21)."""

from __future__ import annotations

import pytest
from engine.config.schema import (
    VisualConfig,
    VisualMaskConfig,
    VisualPerceptualConfig,
    VisualViewportConfig,
)
from pydantic import ValidationError


def test_default_viewports_cover_mobile_tablet_desktop() -> None:
    cfg = VisualConfig()
    names = tuple(vp.name for vp in cfg.viewports)
    assert names == ("mobile", "tablet", "desktop")


def test_default_perceptual_disabled() -> None:
    cfg = VisualConfig()
    assert cfg.perceptual.enabled is False
    assert cfg.perceptual.min_similarity == 0.98


def test_duplicate_viewport_names_rejected() -> None:
    with pytest.raises(ValidationError, match="Duplicate visual.viewports"):
        VisualConfig(
            viewports=(
                VisualViewportConfig(name="mobile", width=375, height=812),
                VisualViewportConfig(name="mobile", width=375, height=900),
            )
        )


def test_viewport_name_constraints() -> None:
    # Name must be lowercase alnum + - _ only.
    with pytest.raises(ValidationError):
        VisualViewportConfig(name="UPPER", width=100, height=100)


def test_mask_requires_selector_or_rect() -> None:
    with pytest.raises(ValidationError, match="selector"):
        VisualMaskConfig(route="home", reason="x")


def test_mask_with_selector_only_is_valid() -> None:
    mask = VisualMaskConfig(route="home", selector="time", reason="clock")
    assert mask.rect is None


def test_perceptual_similarity_range() -> None:
    with pytest.raises(ValidationError):
        VisualPerceptualConfig(min_similarity=1.5)


def test_visual_threshold_range() -> None:
    with pytest.raises(ValidationError):
        VisualConfig(threshold=1.5)
