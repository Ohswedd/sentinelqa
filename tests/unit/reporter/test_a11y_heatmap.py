# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the a11y heatmap renderer."""

from __future__ import annotations

from engine.reporter.a11y_heatmap import (
    HeatmapBox,
    HeatmapPage,
    boxes_from_axe_payload,
    render_heatmap_css,
    render_heatmap_html,
)


def _box(**overrides) -> HeatmapBox:
    base: dict = {
        "x": 10.0,
        "y": 20.0,
        "width": 100.0,
        "height": 40.0,
        "rule_id": "color-contrast",
        "severity": "high",
        "target_selector": "#login",
    }
    base.update(overrides)
    return HeatmapBox(**base)


def test_render_returns_empty_when_no_boxes() -> None:
    page = HeatmapPage(
        screenshot_path="screenshots/home.png",
        image_width_px=1280,
        image_height_px=720,
    )
    assert render_heatmap_html(page) == ""


def test_render_includes_image_and_overlay() -> None:
    page = HeatmapPage(
        screenshot_path="screenshots/home.png",
        image_width_px=1280,
        image_height_px=720,
        boxes=(_box(),),
    )
    html = render_heatmap_html(page)
    assert "<figure" in html
    assert 'src="screenshots/home.png"' in html
    assert "a11y-heatmap-overlay" in html
    assert "a11y-heatmap-box" in html


def test_render_escapes_screenshot_path_and_selector() -> None:
    page = HeatmapPage(
        screenshot_path="screenshots/<x>.png",
        image_width_px=100,
        image_height_px=100,
        boxes=(_box(target_selector="<script>"),),
    )
    html = render_heatmap_html(page)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "screenshots/&lt;x&gt;.png" in html


def test_render_uses_percentage_positions() -> None:
    page = HeatmapPage(
        screenshot_path="x.png",
        image_width_px=1000,
        image_height_px=500,
        boxes=(_box(x=100, y=50, width=200, height=100),),
    )
    html = render_heatmap_html(page)
    assert "left:10.00%" in html
    assert "top:10.00%" in html
    assert "width:20.00%" in html
    assert "height:20.00%" in html


def test_render_handles_zero_image_dimensions() -> None:
    page = HeatmapPage(
        screenshot_path="x.png",
        image_width_px=0,
        image_height_px=0,
        boxes=(_box(),),
    )
    # A zero-dimension image yields no usable rectangles.
    html = render_heatmap_html(page)
    assert "<figure" in html  # still renders the wrapper
    assert "left:" not in html  # no rectangles drawn


def test_render_includes_legend_for_unique_severities() -> None:
    page = HeatmapPage(
        screenshot_path="x.png",
        image_width_px=100,
        image_height_px=100,
        boxes=(
            _box(severity="critical"),
            _box(severity="high"),
            _box(severity="high"),
        ),
    )
    html = render_heatmap_html(page)
    assert "a11y-heatmap-legend" in html
    assert html.count("a11y-heatmap-legend-item") == 2


def test_render_caps_box_count() -> None:
    page = HeatmapPage(
        screenshot_path="x.png",
        image_width_px=1000,
        image_height_px=1000,
        boxes=tuple(_box(x=i, y=i, width=10, height=10) for i in range(120)),
    )
    html = render_heatmap_html(page)
    # Cap is 40 — sample by counting open tags.
    assert html.count('class="a11y-heatmap-box"') == 40


def test_render_heatmap_css_includes_overlay_styles() -> None:
    css = render_heatmap_css()
    assert ".a11y-heatmap{" in css
    assert ".a11y-heatmap-overlay" in css
    assert ".a11y-heatmap-box" in css


# --------------------------------------------------------------------------- #
# Axe payload conversion
# --------------------------------------------------------------------------- #


def test_boxes_from_axe_payload_picks_up_violations() -> None:
    payload = {
        "violations": [
            {
                "id": "color-contrast",
                "impact": "serious",
                "nodes": [
                    {
                        "target": ["#login"],
                        "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
                    }
                ],
            }
        ]
    }
    boxes = boxes_from_axe_payload(payload)
    assert len(boxes) == 1
    assert boxes[0].rule_id == "color-contrast"
    assert boxes[0].severity == "high"
    assert boxes[0].target_selector == "#login"


def test_boxes_from_axe_payload_skips_nodes_without_bbox() -> None:
    payload = {
        "violations": [
            {
                "id": "x",
                "impact": "moderate",
                "nodes": [
                    {"target": [".a"]},  # no bbox
                    {"target": [".b"], "bbox": {"x": 0, "y": 0, "width": 0, "height": 0}},
                    {"target": [".c"], "bbox": {"x": 1, "y": 1, "width": 1, "height": 1}},
                ],
            }
        ]
    }
    boxes = boxes_from_axe_payload(payload)
    assert len(boxes) == 1
    assert boxes[0].target_selector == ".c"


def test_boxes_from_axe_payload_maps_impacts_to_severities() -> None:
    payload = {
        "violations": [
            {"id": "c1", "impact": "critical", "nodes": [_node()]},
            {"id": "c2", "impact": "serious", "nodes": [_node()]},
            {"id": "c3", "impact": "moderate", "nodes": [_node()]},
            {"id": "c4", "impact": "minor", "nodes": [_node()]},
            {"id": "c5", "impact": "unknown", "nodes": [_node()]},
        ]
    }
    boxes = boxes_from_axe_payload(payload)
    by_rule = {b.rule_id: b.severity for b in boxes}
    assert by_rule == {
        "c1": "critical",
        "c2": "high",
        "c3": "medium",
        "c4": "low",
        "c5": "info",
    }


def test_boxes_from_axe_payload_accepts_severity_overrides() -> None:
    payload = {
        "violations": [
            {"id": "c1", "impact": "moderate", "nodes": [_node()]},
        ]
    }
    boxes = boxes_from_axe_payload(payload, severity_by_rule={"c1": "critical"})
    assert boxes[0].severity == "critical"


def test_boxes_from_axe_payload_handles_malformed_payload() -> None:
    assert boxes_from_axe_payload({"violations": "not a list"}) == ()
    assert boxes_from_axe_payload({}) == ()


def test_heatmap_box_area_is_non_negative() -> None:
    assert _box(width=10, height=20).area == 200
    assert _box(width=-1, height=10).area == 0


def _node() -> dict:
    return {"target": [".x"], "bbox": {"x": 1, "y": 1, "width": 1, "height": 1}}
