"""Unit tests for :mod:`modules.visual.diff`."""

from __future__ import annotations

import pytest
from PIL import Image

from modules.visual.diff import pixel_diff, ssim


def _solid(size: tuple[int, int], color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", size, color)


def test_pixel_diff_identical_zero() -> None:
    a = _solid((10, 10), (10, 10, 10))
    b = _solid((10, 10), (10, 10, 10))
    result = pixel_diff(a, b)
    assert result.differing_pixels == 0
    assert result.fraction == 0.0
    assert result.total_pixels == 100


def test_pixel_diff_one_pixel_changed() -> None:
    a = _solid((10, 10), (255, 255, 255))
    b = a.copy()
    b.putpixel((0, 0), (0, 0, 0))
    result = pixel_diff(a, b)
    assert result.differing_pixels == 1
    assert result.fraction == pytest.approx(0.01)


def test_pixel_diff_size_mismatch_raises() -> None:
    a = _solid((4, 4), (0, 0, 0))
    b = _solid((5, 4), (0, 0, 0))
    with pytest.raises(ValueError, match="size mismatch"):
        pixel_diff(a, b)


def test_pixel_diff_overlay_has_red_at_changed_pixel() -> None:
    a = _solid((4, 4), (255, 255, 255))
    b = a.copy()
    b.putpixel((1, 2), (0, 0, 0))
    result = pixel_diff(a, b)
    pixel = result.overlay.getpixel((1, 2))
    assert isinstance(pixel, tuple)
    assert pixel[:3] == (255, 0, 0)


def test_ssim_identical_is_one() -> None:
    a = _solid((8, 8), (128, 128, 128))
    assert ssim(a, a) == pytest.approx(1.0)


def test_ssim_completely_different_below_one() -> None:
    a = _solid((8, 8), (0, 0, 0))
    b = _solid((8, 8), (255, 255, 255))
    value = ssim(a, b)
    assert 0.0 <= value < 1.0
    assert value < 0.5


def test_ssim_size_mismatch_raises() -> None:
    a = _solid((4, 4), (0, 0, 0))
    b = _solid((5, 4), (0, 0, 0))
    with pytest.raises(ValueError, match="size mismatch"):
        ssim(a, b)


def test_ssim_empty_image_returns_one() -> None:
    a = Image.new("RGB", (0, 0), (0, 0, 0))
    b = Image.new("RGB", (0, 0), (0, 0, 0))
    assert ssim(a, b) == 1.0


def test_pixel_diff_zero_total_yields_zero_fraction() -> None:
    a = Image.new("RGB", (0, 0), (0, 0, 0))
    b = Image.new("RGB", (0, 0), (0, 0, 0))
    result = pixel_diff(a, b)
    assert result.fraction == 0.0
