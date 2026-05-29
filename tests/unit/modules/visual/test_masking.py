"""Unit tests for :mod:`modules.visual.masking` (Phase 21.04)."""

from __future__ import annotations

import pytest
from engine.config.schema import VisualMaskConfig
from PIL import Image

from modules.visual.diff import pixel_diff
from modules.visual.masking import MASK_FILL, apply_masks, select_masks


def _solid(size: tuple[int, int], color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", size, color)


def _mask(
    route: str, *, rect: tuple[int, int, int, int] | None = None, selector: str | None = None
) -> VisualMaskConfig:
    return VisualMaskConfig(route=route, rect=rect, selector=selector, reason=f"mask for {route}")


def test_select_masks_exact_match() -> None:
    masks = (_mask("home", rect=(0, 0, 1, 1)), _mask("about", rect=(0, 0, 1, 1)))
    assert select_masks(masks, "home") == (masks[0],)


def test_select_masks_wildcard_route_matches_all() -> None:
    masks = (_mask("*", rect=(0, 0, 1, 1)),)
    assert select_masks(masks, "anywhere") == masks


def test_select_masks_prefix_glob() -> None:
    masks = (_mask("admin*", rect=(0, 0, 1, 1)),)
    assert select_masks(masks, "admin_dashboard") == masks
    assert select_masks(masks, "home") == ()


def test_apply_masks_paints_rect_to_fill_colour() -> None:
    img = _solid((10, 10), (255, 255, 255))
    masks = (_mask("home", rect=(2, 2, 4, 4)),)
    out, applied = apply_masks(img, masks, route_slug="home")
    assert applied[0].rect == (2, 2, 4, 4)
    assert applied[0].reason.startswith("mask for")
    inside = out.getpixel((3, 3))
    assert isinstance(inside, tuple)
    assert inside[:3] == MASK_FILL[:3]
    outside = out.getpixel((0, 0))
    assert isinstance(outside, tuple)
    assert outside[:3] == (255, 255, 255)


def test_apply_masks_clamps_to_image_bounds() -> None:
    img = _solid((5, 5), (0, 0, 0))
    masks = (_mask("home", rect=(3, 3, 100, 100)),)
    out, applied = apply_masks(img, masks, route_slug="home")
    assert applied[0].rect == (3, 3, 2, 2)
    pixel = out.getpixel((4, 4))
    assert isinstance(pixel, tuple)
    assert pixel[:3] == MASK_FILL[:3]


def test_apply_masks_selector_only_does_not_paint() -> None:
    img = _solid((5, 5), (255, 255, 255))
    masks = (_mask("home", selector="time"),)
    out, applied = apply_masks(img, masks, route_slug="home")
    assert applied[0].rect is None
    # Image unchanged for selector-only masks.
    pixel = out.getpixel((0, 0))
    assert isinstance(pixel, tuple)
    assert pixel[:3] == (255, 255, 255)


def test_apply_masks_negative_rect_is_recorded_but_not_drawn() -> None:
    img = _solid((5, 5), (255, 255, 255))
    masks = (_mask("home", rect=(10, 10, 0, 0)),)
    out, applied = apply_masks(img, masks, route_slug="home")
    assert applied[0].rect == (5, 5, 0, 0)
    pixel = out.getpixel((0, 0))
    assert isinstance(pixel, tuple)
    assert pixel[:3] == (255, 255, 255)


def test_masking_stabilises_diff_under_dynamic_region() -> None:
    """Masked dynamic regions should not raise the diff fraction."""

    base = _solid((10, 10), (255, 255, 255))
    # Simulate a "clock" that updates: change a 4x4 region in the second
    # capture only.
    current = base.copy()
    for x in range(2, 6):
        for y in range(2, 6):
            current.putpixel((x, y), (0, 0, 0))

    # Without mask: 16 pixels differ.
    raw = pixel_diff(base, current)
    assert raw.differing_pixels == 16

    masks = (_mask("home", rect=(2, 2, 4, 4)),)
    masked_base, _ = apply_masks(base, masks, route_slug="home")
    masked_cur, _ = apply_masks(current, masks, route_slug="home")
    masked_diff = pixel_diff(masked_base, masked_cur)
    assert masked_diff.differing_pixels == 0


def test_visual_mask_config_requires_selector_or_rect() -> None:
    with pytest.raises(ValueError, match="selector"):
        VisualMaskConfig(route="home", reason="x")
