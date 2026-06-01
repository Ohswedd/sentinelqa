# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the image-optimisation check."""

from __future__ import annotations

from modules.performance.checks.image_optim import (
    HEAVY_BYTES,
    collect_image_stats,
    find_image_findings,
)


def test_collect_image_stats_returns_one_per_img() -> None:
    html = '<img src="a.jpg"><img src="b.png" width="100" height="100">'
    stats = collect_image_stats(html)
    assert len(stats) == 2
    assert stats[1].attrs["width"] == "100"


def test_collect_recognises_picture_block_with_webp_source() -> None:
    html = (
        "<picture>"
        '<source type="image/webp" srcset="a.webp">'
        '<source type="image/avif" srcset="a.avif">'
        '<img src="a.jpg">'
        "</picture>"
    )
    stats = collect_image_stats(html)
    assert stats[0].in_picture_block
    assert stats[0].in_picture_offers_webp_or_avif


def test_heavy_jpeg_without_modern_fallback_is_flagged() -> None:
    html = '<img src="hero.jpg" width="1000" height="500">'
    stats = collect_image_stats(html, sizes_by_src={"hero.jpg": HEAVY_BYTES + 1})
    findings = find_image_findings(stats)
    codes = {f.code for f in findings}
    assert "IMG-HEAVY-LEGACY" in codes


def test_heavy_jpeg_inside_picture_with_webp_is_not_flagged() -> None:
    html = (
        "<picture>"
        '<source type="image/webp" srcset="hero.webp">'
        '<img src="hero.jpg" width="1000" height="500">'
        "</picture>"
    )
    stats = collect_image_stats(html, sizes_by_src={"hero.jpg": HEAVY_BYTES + 1})
    findings = find_image_findings(stats)
    codes = {f.code for f in findings}
    assert "IMG-HEAVY-LEGACY" not in codes


def test_below_fold_image_without_lazy_is_flagged() -> None:
    html = "".join(f'<img src="img{i}.jpg" width="100" height="100">' for i in range(5))
    stats = collect_image_stats(html)
    findings = find_image_findings(stats)
    no_lazy = [f for f in findings if f.code == "IMG-NO-LAZY"]
    assert len(no_lazy) == 3  # images 2, 3, 4 (0-indexed: 2, 3, 4)


def test_above_fold_images_not_flagged_for_lazy() -> None:
    html = '<img src="a.jpg" width="100" height="100">' '<img src="b.jpg" width="100" height="100">'
    stats = collect_image_stats(html)
    findings = find_image_findings(stats)
    assert all(f.code != "IMG-NO-LAZY" for f in findings)


def test_missing_dimensions_flagged_as_cls_risk() -> None:
    html = '<img src="x.jpg">'
    stats = collect_image_stats(html)
    findings = find_image_findings(stats)
    codes = {f.code for f in findings}
    assert "IMG-NO-DIMENSIONS" in codes


def test_a11y_overlap_opt_in() -> None:
    html = '<img src="x.jpg" width="100" height="100">'
    stats = collect_image_stats(html)
    without = find_image_findings(stats, include_a11y_overlap=False)
    with_a11y = find_image_findings(stats, include_a11y_overlap=True)
    assert all(f.code != "IMG-NO-ALT" for f in without)
    assert any(f.code == "IMG-NO-ALT" for f in with_a11y)


def test_unknown_size_skips_heavy_jpeg_rule() -> None:
    html = '<img src="x.jpg" width="100" height="100">'
    stats = collect_image_stats(html)
    findings = find_image_findings(stats)
    assert all(f.code != "IMG-HEAVY-LEGACY" for f in findings)


def test_attr_parser_handles_unquoted_attributes() -> None:
    html = "<img src=foo.png loading=lazy>"
    stats = collect_image_stats(html)
    # The unquoted parser only collects fully-quoted attrs robustly; this
    # behaviour test simply guards against crashes on real-world HTML.
    assert len(stats) == 1
