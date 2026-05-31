# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Brand PNG generator (Phase 35.05).

Renders the SentinelQA primary mark and favicons to PNG at the
sizes documented in `plans/phase-35-public-release/05-brand-assets.md`
using Pillow (no system SVG renderer required). The design here is a
faithful translation of `docs/assets/brand/logo.svg` — the shield
silhouette, gradient, bevel, and monogram. Pillow does not render SVG
natively, so the geometry is reproduced procedurally so the output
matches the SVG within a few pixels at any size.

Run via::

    python -m scripts.release.gen_brand_pngs

The script is deterministic — same Pillow version → byte-identical
output — so the generated PNGs are safe to commit and the audit /
test layer can pin their presence.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAND_DIR = REPO_ROOT / "docs" / "assets" / "brand"

# Palette mirrors docs/assets/brand/logo.svg.
BRAND_TOP = (15, 118, 110)  # #0f766e
BRAND_BOTTOM = (8, 47, 73)  # #082f49
BRAND_BEVEL = (34, 211, 238)  # #22d3ee
BRAND_TEXT = (240, 253, 250)  # #f0fdfa
BRAND_BG_OG = (15, 23, 42)  # #0f172a (slate-900) for social preview


def _vertical_gradient(size: tuple[int, int]) -> Image.Image:
    """Linear gradient mimicking the SVG `defs linearGradient`."""
    w, h = size
    base = Image.new("RGB", size, BRAND_TOP)
    px = base.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(BRAND_TOP[0] + (BRAND_BOTTOM[0] - BRAND_TOP[0]) * t)
        g = int(BRAND_TOP[1] + (BRAND_BOTTOM[1] - BRAND_TOP[1]) * t)
        b = int(BRAND_TOP[2] + (BRAND_BOTTOM[2] - BRAND_TOP[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return base


def _shield_polygon(size: int, inset: float = 0.0) -> list[tuple[float, float]]:
    """Shield path equivalent to SVG `M128 16 L224 48 L224 128 C... L32 48 Z`."""
    s = size
    # Express the geometry as fractions of the original 256-unit viewBox.
    pts_norm = [
        (128, 16),
        (224, 48),
        (224, 128),
        (200, 192),
        (164, 220),
        (128, 240),
        (92, 220),
        (56, 192),
        (32, 128),
        (32, 48),
    ]
    # Apply optional inset so we can render a bevel inside the shield.
    centroid_x = sum(p[0] for p in pts_norm) / len(pts_norm)
    centroid_y = sum(p[1] for p in pts_norm) / len(pts_norm)
    out: list[tuple[float, float]] = []
    for x, y in pts_norm:
        if inset:
            dx = x - centroid_x
            dy = y - centroid_y
            distance = math.hypot(dx, dy)
            if distance > 0:
                shrink = max(0.0, 1.0 - (inset / distance))
                x = centroid_x + dx * shrink
                y = centroid_y + dy * shrink
        out.append((x * s / 256, y * s / 256))
    return out


def _load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Pillow ships `DejaVuSans-Bold` with most installs; the system
    # font search is intentionally narrow so the generator is portable.
    candidates = [
        "DejaVuSans-Bold.ttf",
        "Arial Bold.ttf",
        "Helvetica-Bold.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_logo(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Shield body — paint via a clipped gradient.
    shield_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(shield_mask).polygon(_shield_polygon(size), fill=255)
    gradient = _vertical_gradient((size, size)).convert("RGBA")
    img.paste(gradient, (0, 0), shield_mask)

    # Outer stroke.
    draw.polygon(
        _shield_polygon(size),
        outline=BRAND_TOP,
        width=max(2, size // 64),
    )
    # Inner bevel.
    draw.polygon(
        _shield_polygon(size, inset=size * 0.06),
        outline=BRAND_BEVEL,
        width=max(1, size // 128),
    )

    # Monogram.
    text = "SQ"
    font = _load_font(int(size * 0.38))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1] + size * 0.04  # nudge baseline down
    draw.text((tx, ty), text, fill=BRAND_TEXT, font=font)
    return img


def _draw_favicon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Rounded square.
    radius = max(2, size // 6)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=BRAND_TOP)
    # Single letter "S" — best legibility at 16x16.
    text = "S"
    font = _load_font(int(size * 0.72))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1] + size * 0.04
    draw.text((tx, ty), text, fill=BRAND_TEXT, font=font)
    return img


def _draw_social_preview(width: int = 1280, height: int = 640) -> Image.Image:
    img = Image.new("RGB", (width, height), BRAND_BG_OG)
    draw = ImageDraw.Draw(img)

    # Logo plate on the left.
    plate = _draw_logo(480).convert("RGBA")
    img.paste(plate, (80, (height - 480) // 2), plate)

    # Title + tagline on the right.
    title_font = _load_font(96)
    sub_font = _load_font(36)
    micro_font = _load_font(28)

    text_x = 640
    draw.text((text_x, 180), "SentinelQA", fill=BRAND_TEXT, font=title_font)
    draw.text(
        (text_x, 300),
        "Release-confidence for LLM-built apps.",
        fill=(186, 230, 253),
        font=sub_font,
    )
    draw.text(
        (text_x, 360),
        "Playwright-native. Evidence-backed. Authorized-only.",
        fill=(186, 230, 253),
        font=sub_font,
    )
    draw.text(
        (text_x, 460),
        "github.com/Ohswedd/sentinelqa  ·  docs.sentinelqa.dev",
        fill=(125, 211, 252),
        font=micro_font,
    )
    return img


_TARGETS = [
    ("logo-256.png", lambda: _draw_logo(256)),
    ("logo-512.png", lambda: _draw_logo(512)),
    ("logo-1024.png", lambda: _draw_logo(1024)),
    ("favicon-16.png", lambda: _draw_favicon(16)),
    ("favicon-32.png", lambda: _draw_favicon(32)),
    ("apple-touch-icon-180.png", lambda: _draw_favicon(180)),
    ("social-preview-1280x640.png", lambda: _draw_social_preview(1280, 640)),
]


def main() -> int:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    for name, factory in _TARGETS:
        out = BRAND_DIR / name
        img = factory()
        # Use save without optimize to keep the output stable across
        # Pillow versions (optimize=True changes IDAT chunk order).
        img.save(out, format="PNG")
        print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
