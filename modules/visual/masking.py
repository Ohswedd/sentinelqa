"""Dynamic-content masking (Phase 21.04, PRD §10.6, CLAUDE §29).

The Python diff layer paints user-specified rectangles to a neutral
fill colour on BOTH baseline and current before pixel comparison.
``visual.masks`` entries can supply either:

- ``rect`` — explicit ``(x, y, w, h)``, applied at diff time. Useful
  for fixtures that don't drive a real browser.
- ``selector`` — a CSS selector the TS capture helper hides before the
  screenshot. The diff layer can't recompute the selector's bounding
  box without DOM access, so selector-only masks contribute their
  ``reason`` to the recorded ``masks_applied`` list but do not paint
  on the Python side. (The TS capture layer is responsible for hiding
  the element before the screenshot is written.)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from engine.config.schema import VisualMaskConfig
from PIL import Image, ImageDraw

# Solid grey — visually obvious in diff overlays, low contrast so it
# doesn't trip the perceptual SSIM check on its own.
MASK_FILL: tuple[int, int, int, int] = (127, 127, 127, 255)


@dataclass(frozen=True)
class AppliedMask:
    """Record of one mask the diff layer painted (or noted)."""

    route_slug: str
    reason: str
    rect: tuple[int, int, int, int] | None  # None when selector-only


def select_masks(
    masks: tuple[VisualMaskConfig, ...],
    route_slug: str,
) -> tuple[VisualMaskConfig, ...]:
    """Return masks that target ``route_slug``.

    Matching is exact OR by glob-style prefix ``*``. ``route="*"`` is the
    wildcard for every route.
    """

    selected: list[VisualMaskConfig] = []
    for mask in masks:
        if mask.route == "*" or mask.route == route_slug:
            selected.append(mask)
            continue
        if mask.route.endswith("*") and route_slug.startswith(mask.route[:-1]):
            selected.append(mask)
    return tuple(selected)


def apply_masks(
    image: Image.Image,
    masks: Iterable[VisualMaskConfig],
    *,
    route_slug: str,
) -> tuple[Image.Image, tuple[AppliedMask, ...]]:
    """Return ``image`` with rect-masks painted + the list of records.

    The image is copied (Pillow draws in place); the caller can safely
    discard the original. Selector-only masks are recorded but not
    painted (the TS capture is responsible).
    """

    copy = image.copy()
    draw = ImageDraw.Draw(copy, mode="RGBA")
    applied: list[AppliedMask] = []
    width, height = copy.size
    for mask in masks:
        if mask.rect is None:
            applied.append(
                AppliedMask(
                    route_slug=route_slug,
                    reason=mask.reason,
                    rect=None,
                )
            )
            continue
        x, y, w, h = mask.rect
        x = max(0, min(x, width))
        y = max(0, min(y, height))
        x2 = max(0, min(x + w, width))
        y2 = max(0, min(y + h, height))
        if x2 <= x or y2 <= y:
            # Empty rect after clamping — record but do not draw.
            applied.append(
                AppliedMask(
                    route_slug=route_slug,
                    reason=mask.reason,
                    rect=(x, y, 0, 0),
                )
            )
            continue
        draw.rectangle((x, y, x2 - 1, y2 - 1), fill=MASK_FILL)
        applied.append(
            AppliedMask(
                route_slug=route_slug,
                reason=mask.reason,
                rect=(x, y, x2 - x, y2 - y),
            )
        )
    return copy, tuple(applied)


__all__ = ["AppliedMask", "MASK_FILL", "apply_masks", "select_masks"]
