# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Cheap-but-useful image optimisation audit (v1.3.0).

Scans the discovered HTML for ``<img>`` tags and flags the patterns
that contribute most to the "images" portion of a typical Lighthouse
budget:

* Heavy raster images (> ``HEAVY_BYTES`` JPEG/PNG) without a
  ``<source>`` ladder offering WebP / AVIF fallbacks.
* ``<img>`` tags below the fold without ``loading="lazy"``.
* ``<img>`` tags missing ``width``/``height`` (causes CLS).
* Missing ``alt`` attribute (overlaps with the a11y module — listed
  here only when explicitly requested via ``include_a11y_overlap``).

Pure HTML scan, no IO. The image-size value can come from
discovery's HTTP response (the actual response Content-Length); when
that information isn't available the caller passes ``None`` and the
size-based rules are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Literal

Severity = Literal["critical", "high", "medium", "low", "info"]

HEAVY_BYTES: Final[int] = 200 * 1024  # 200 KiB
ABOVE_FOLD_NTH: Final[int] = 2  # first 2 images are considered above-fold

_IMG_RE = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)
_PICTURE_BLOCK_RE = re.compile(
    r"<picture\b[^>]*>(.*?)</picture>",
    re.IGNORECASE | re.DOTALL,
)
_SOURCE_RE = re.compile(r"<source\b[^>]*type\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_ATTR_RE = re.compile(
    r'([a-zA-Z_:][\w:-]*)\s*=\s*"([^"]*)"|([a-zA-Z_:][\w:-]*)\s*=\s*\'([^\']*)\'|([a-zA-Z_:][\w:-]*)'
)


@dataclass(frozen=True, slots=True)
class ImageFinding:
    code: str
    severity: Severity
    src: str
    rationale: str


@dataclass(frozen=True, slots=True)
class ImageStat:
    src: str
    bytes: int | None = None
    in_picture_block: bool = False
    in_picture_offers_webp_or_avif: bool = False
    attrs: dict[str, str] = field(default_factory=dict)


def _parse_attrs(attrs: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _ATTR_RE.finditer(attrs):
        k_dq, v_dq, k_sq, v_sq, k_bare = match.groups()
        if k_dq:
            out[k_dq.lower()] = v_dq
        elif k_sq:
            out[k_sq.lower()] = v_sq
        elif k_bare:
            out[k_bare.lower()] = ""
    return out


def collect_image_stats(
    html: str,
    *,
    sizes_by_src: dict[str, int] | None = None,
) -> tuple[ImageStat, ...]:
    """Extract every ``<img>`` and its surrounding context."""

    sizes = sizes_by_src or {}
    out: list[ImageStat] = []
    picture_imgs: set[int] = set()
    picture_with_modern: set[int] = set()

    for pic_match in _PICTURE_BLOCK_RE.finditer(html):
        body = pic_match.group(1)
        sources = _SOURCE_RE.findall(body)
        modern = any(t.lower() in {"image/webp", "image/avif"} for t in sources)
        # All <img> within this picture range belong to it.
        for img in _IMG_RE.finditer(body):
            picture_imgs.add(img.start() + pic_match.start(1))
            if modern:
                picture_with_modern.add(img.start() + pic_match.start(1))

    for img in _IMG_RE.finditer(html):
        attrs = _parse_attrs(img.group(1))
        src = attrs.get("src") or attrs.get("data-src") or ""
        bytes_ = sizes.get(src)
        out.append(
            ImageStat(
                src=src,
                bytes=bytes_,
                in_picture_block=img.start() in picture_imgs,
                in_picture_offers_webp_or_avif=img.start() in picture_with_modern,
                attrs=attrs,
            )
        )
    return tuple(out)


def find_image_findings(
    stats: tuple[ImageStat, ...],
    *,
    include_a11y_overlap: bool = False,
) -> tuple[ImageFinding, ...]:
    """Return findings for the heaviest patterns."""

    out: list[ImageFinding] = []
    for index, stat in enumerate(stats):
        if not stat.src:
            continue

        # 1) Heavy raster without modern alternatives.
        if (
            stat.bytes is not None
            and stat.bytes > HEAVY_BYTES
            and _is_legacy_raster(stat.src)
            and not (stat.in_picture_block and stat.in_picture_offers_webp_or_avif)
        ):
            out.append(
                ImageFinding(
                    code="IMG-HEAVY-LEGACY",
                    severity="medium",
                    src=stat.src,
                    rationale=(
                        f"{stat.bytes/1024:.0f} KiB JPEG/PNG without a "
                        "<picture> ladder offering WebP/AVIF. Modern "
                        "encoders cut payload by 25-50% for the same "
                        "visual quality."
                    ),
                )
            )

        # 2) Missing loading=lazy on a below-fold image.
        if index >= ABOVE_FOLD_NTH and stat.attrs.get("loading") != "lazy":
            out.append(
                ImageFinding(
                    code="IMG-NO-LAZY",
                    severity="low",
                    src=stat.src,
                    rationale=(
                        f"Image #{index + 1} is below-fold and has no "
                        '``loading="lazy"`` attribute. Lazy-loading defers '
                        "fetch until the browser scrolls it into view, "
                        "saving LCP-blocking bandwidth."
                    ),
                )
            )

        # 3) Missing width/height (CLS contributor).
        if "width" not in stat.attrs or "height" not in stat.attrs:
            out.append(
                ImageFinding(
                    code="IMG-NO-DIMENSIONS",
                    severity="low",
                    src=stat.src,
                    rationale=(
                        "Image has no width/height attributes. The browser "
                        "cannot reserve layout space until the image arrives, "
                        "contributing to Cumulative Layout Shift."
                    ),
                )
            )

        # 4) Missing alt — only when caller opted in.
        if include_a11y_overlap and "alt" not in stat.attrs:
            out.append(
                ImageFinding(
                    code="IMG-NO-ALT",
                    severity="medium",
                    src=stat.src,
                    rationale=(
                        "Image has no alt attribute. Screen readers will "
                        "announce the filename, harming accessibility."
                    ),
                )
            )

    return tuple(out)


def _is_legacy_raster(src: str) -> bool:
    lowered = src.lower().split("?", 1)[0]
    return lowered.endswith((".jpg", ".jpeg", ".png"))


__all__ = [
    "HEAVY_BYTES",
    "ImageFinding",
    "ImageStat",
    "collect_image_stats",
    "find_image_findings",
]
