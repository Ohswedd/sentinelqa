"""Pixel diff + perceptual SSIM (Phase 21.03, PRD §10.6, CLAUDE §29).

Two diff layers ship:

- :func:`pixel_diff` — pure pixel comparison. Returns the number of
  differing pixels, the diff fraction, and a coloured overlay image
  (red where pixels differ).
- :func:`ssim` — single-scale structural similarity index, computed on
  the luminance channel. Returned in ``[0.0, 1.0]`` where 1.0 means
  identical. The perceptual layer is a *noise filter*: a finding only
  fires when BOTH the pixel threshold AND the SSIM threshold cross,
  so flicker / sub-pixel renderer drift doesn't generate noise.

Both functions operate on Pillow ``Image`` objects (RGB / RGBA). The
images must be the same size; size-mismatch is the caller's signal to
emit a ``size_mismatch`` finding rather than coerce-and-compare.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageChops


@dataclass(frozen=True)
class PixelDiffResult:
    """Output of :func:`pixel_diff`."""

    width: int
    height: int
    total_pixels: int
    differing_pixels: int
    overlay: Image.Image

    @property
    def fraction(self) -> float:
        if self.total_pixels == 0:
            return 0.0
        return self.differing_pixels / self.total_pixels


def pixel_diff(
    baseline: Image.Image,
    current: Image.Image,
) -> PixelDiffResult:
    """Compare two same-sized images at pixel granularity.

    The overlay is a copy of ``baseline`` with differing pixels
    repainted bright red (and the rest darkened to 40% luminance) so a
    human reviewing the diff PNG can find the changed region quickly.
    """

    if baseline.size != current.size:
        raise ValueError(
            f"pixel_diff: size mismatch {baseline.size!r} vs {current.size!r}. "
            "Caller is expected to handle this before invoking pixel_diff."
        )

    base_rgba = baseline.convert("RGBA")
    cur_rgba = current.convert("RGBA")
    width, height = base_rgba.size
    total = width * height

    # Per-channel absolute difference; collapse to a binary mask where
    # *any* channel differs.
    delta = ImageChops.difference(base_rgba, cur_rgba)
    mask = delta.convert("L").point(lambda v: 255 if v > 0 else 0).convert("1")
    differing = int(sum(1 for px in list(mask.getdata()) if px))

    # Build the overlay: darken baseline, then OR-paint red where the
    # mask is set. This is the "diff overlay" the report links to.
    overlay = base_rgba.copy()
    darkened = overlay.point(lambda v: int(v * 0.4))
    overlay.paste(darkened, mask=None)
    red = Image.new("RGBA", overlay.size, (255, 0, 0, 255))
    overlay.paste(red, mask=mask)

    return PixelDiffResult(
        width=width,
        height=height,
        total_pixels=total,
        differing_pixels=differing,
        overlay=overlay,
    )


def _luminance_bytes(image: Image.Image) -> bytes:
    """Return ITU BT.601 luminance bytes for an RGB / RGBA image."""

    return image.convert("L").tobytes()


def ssim(baseline: Image.Image, current: Image.Image) -> float:
    """Return the structural similarity index in ``[0.0, 1.0]``.

    Single-scale, computed on the luminance channel using the global
    Wang et al. formulation (no Gaussian window — block-stable). For
    visual-regression noise filtering, single-scale SSIM is the right
    altitude: faster than MS-SSIM, more robust than peak-signal-to-
    noise, and the published constants ``C1``/``C2`` keep the formula
    deterministic across platforms.
    """

    if baseline.size != current.size:
        raise ValueError(f"ssim: size mismatch {baseline.size!r} vs {current.size!r}.")
    width, height = baseline.size
    n = width * height
    if n == 0:
        return 1.0

    base = _luminance_bytes(baseline)
    cur = _luminance_bytes(current)

    # Single-pass means + cross statistics.
    sum_x = sum_y = sum_x2 = sum_y2 = sum_xy = 0
    for x_byte, y_byte in zip(base, cur, strict=False):
        sum_x += x_byte
        sum_y += y_byte
        sum_x2 += x_byte * x_byte
        sum_y2 += y_byte * y_byte
        sum_xy += x_byte * y_byte

    mu_x = sum_x / n
    mu_y = sum_y / n
    var_x = (sum_x2 / n) - mu_x * mu_x
    var_y = (sum_y2 / n) - mu_y * mu_y
    cov = (sum_xy / n) - mu_x * mu_y

    L = 255.0  # noqa: N806 — published constant name (dynamic range).
    k1, k2 = 0.01, 0.03
    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2

    numerator = (2 * mu_x * mu_y + c1) * (2 * cov + c2)
    denominator = (mu_x * mu_x + mu_y * mu_y + c1) * (var_x + var_y + c2)
    if denominator == 0.0:
        return 1.0
    value = numerator / denominator
    # Clamp tiny floating-point overshoots to [0, 1] so callers can
    # compare with min_similarity without epsilon contortions.
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))


__all__ = ["PixelDiffResult", "pixel_diff", "ssim"]
