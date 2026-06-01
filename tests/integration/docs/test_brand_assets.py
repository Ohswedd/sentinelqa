# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Brand-asset health.

Asserts every brand asset listed in `docs/dev/brand.md` is present on
disk, valid PNG/SVG, and wired into the docs site `<head>` where the
spec requires it.
"""

from __future__ import annotations

import struct
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BRAND_DIR = REPO_ROOT / "docs" / "assets" / "brand"
DOCS_PUBLIC = REPO_ROOT / "apps" / "docs" / "public"
ASTRO_CONFIG = REPO_ROOT / "apps" / "docs" / "astro.config.mjs"
BRAND_DOC = REPO_ROOT / "docs" / "dev" / "brand.md"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# (filename, expected width, expected height) — None means "skip
# dimension check" (only SVGs).
ASSETS: tuple[tuple[str, int | None, int | None], ...] = (
    ("logo.svg", None, None),
    ("logo-256.png", 256, 256),
    ("logo-512.png", 512, 512),
    ("logo-1024.png", 1024, 1024),
    ("favicon.svg", None, None),
    ("favicon-16.png", 16, 16),
    ("favicon-32.png", 32, 32),
    ("apple-touch-icon-180.png", 180, 180),
    ("social-preview-1280x640.png", 1280, 640),
)


def _read_png_dimensions(path: Path) -> tuple[int, int]:
    """Parse the PNG IHDR chunk to extract width/height."""
    data = path.read_bytes()
    if not data.startswith(PNG_MAGIC):
        raise AssertionError(f"{path} is not a valid PNG (missing magic)")
    # The IHDR chunk follows the magic: 4 bytes length, 4 bytes type,
    # then 13 bytes of data starting with width (4) + height (4).
    if data[12:16] != b"IHDR":
        raise AssertionError(f"{path} does not start with an IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _is_valid_svg(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return "<svg" in text and "</svg>" in text


def test_brand_directory_present() -> None:
    assert BRAND_DIR.is_dir(), f"brand directory missing: {BRAND_DIR}"


def test_every_brand_asset_present_and_valid() -> None:
    failures: list[str] = []
    for name, expected_w, expected_h in ASSETS:
        path = BRAND_DIR / name
        if not path.is_file():
            failures.append(f"missing: {path}")
            continue
        if name.endswith(".svg"):
            if not _is_valid_svg(path):
                failures.append(f"invalid SVG: {path}")
            continue
        try:
            w, h = _read_png_dimensions(path)
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        if expected_w is not None and (w, h) != (expected_w, expected_h):
            failures.append(f"{path}: expected {expected_w}x{expected_h}, got {w}x{h}")
    assert not failures, "Brand-asset failures:\n" + "\n".join(failures)


def test_favicons_and_og_served_from_docs_public() -> None:
    """Astro serves the favicons + OG image from apps/docs/public/."""
    required = (
        "favicon.svg",
        "favicon-16.png",
        "favicon-32.png",
        "apple-touch-icon-180.png",
        "social-preview-1280x640.png",
    )
    missing = [name for name in required if not (DOCS_PUBLIC / name).is_file()]
    assert not missing, (
        "apps/docs/public/ is missing assets that the Starlight `head` "
        f"config refers to: {missing}. Copy them from docs/assets/brand/."
    )


def test_astro_config_wires_favicons_and_og_image() -> None:
    text = ASTRO_CONFIG.read_text(encoding="utf-8")
    # Starlight's `favicon` shortcut for the SVG.
    assert (
        "favicon: '/favicon.svg'" in text or 'favicon: "/favicon.svg"' in text
    ), "astro.config.mjs must set the Starlight `favicon` config to /favicon.svg."
    # PNG favicon link tags.
    for sized in ("favicon-16.png", "favicon-32.png", "apple-touch-icon-180.png"):
        assert sized in text, f"astro.config.mjs must link to /{sized} in `head`."
    # Open Graph + Twitter Card image.
    assert "og:image" in text
    assert "twitter:image" in text
    assert "social-preview-1280x640.png" in text


def test_brand_doc_present_and_documents_usage_rules() -> None:
    assert BRAND_DOC.is_file(), f"brand doc missing at {BRAND_DOC}"
    text = BRAND_DOC.read_text(encoding="utf-8")
    # The doc must restate the name spelling, the assets table, the
    # usage do's, the usage don'ts, and the pre-1.0 placeholder note.
    for marker in (
        "SentinelQA",
        "logo.svg",
        "What you may do",
        "What requires permission",
        "Pre-1.0 status",
    ):
        assert marker in text, f"docs/dev/brand.md missing section: {marker}"


def test_logo_svg_declares_brand_palette() -> None:
    text = (BRAND_DIR / "logo.svg").read_text(encoding="utf-8")
    # The placeholder design uses two palette anchors. If the palette
    # changes, the test should be updated alongside the design.
    for color in ("#0f766e", "#082f49"):
        assert color in text, (
            f"logo.svg must declare brand color {color}; if the palette "
            "changed, update the test in lockstep with the design."
        )
