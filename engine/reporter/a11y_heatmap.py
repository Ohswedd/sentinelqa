# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Accessibility-finding heatmap overlay (v1.6.0).

When the a11y module captures a screenshot AND per-violation
bounding boxes (from Playwright's ``locator.boundingBox()``), the
reporter can overlay translucent coloured rectangles on the
screenshot showing which DOM elements triggered which axe rules.

This module is the pure renderer: given a screenshot and a list of
:class:`HeatmapBox` records it returns an HTML fragment + the
inline CSS the reporter inlines into ``report.html``.

The actual capture flow is the module shell's job (Playwright +
axe-core); this file keeps the rendering testable without a browser.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from html import escape
from typing import Any, Final, Literal

SeverityKind = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class HeatmapBox:
    """One bounding rectangle for an axe-violating element."""

    x: float
    y: float
    width: float
    height: float
    rule_id: str
    severity: SeverityKind
    target_selector: str = ""

    @property
    def area(self) -> float:
        return max(self.width, 0) * max(self.height, 0)


@dataclass(frozen=True, slots=True)
class HeatmapPage:
    """Inputs for one heatmap render."""

    screenshot_path: str  # POSIX-relative to the run dir
    image_width_px: int
    image_height_px: int
    boxes: tuple[HeatmapBox, ...] = field(default_factory=tuple)


# Colour ramp matches the audit's standard severity ladder. Alpha is
# bumped on critical so the eye lands there first.
_SEVERITY_COLOR: Final[dict[SeverityKind, str]] = {
    "critical": "rgba(220, 38, 38, 0.55)",
    "high": "rgba(234, 88, 12, 0.45)",
    "medium": "rgba(202, 138, 4, 0.40)",
    "low": "rgba(132, 204, 22, 0.30)",
    "info": "rgba(96, 165, 250, 0.30)",
}

_BORDER_COLOR: Final[dict[SeverityKind, str]] = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#ca8a04",
    "low": "#84cc16",
    "info": "#60a5fa",
}


_MAX_BOXES_PER_PAGE: Final[int] = 40


def _clamp_unit(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _render_box(box: HeatmapBox, page: HeatmapPage, index: int) -> str:
    """Render one absolutely-positioned ``<div>`` overlay."""

    if page.image_width_px <= 0 or page.image_height_px <= 0:
        return ""
    left = _clamp_unit(box.x / page.image_width_px) * 100
    top = _clamp_unit(box.y / page.image_height_px) * 100
    width = _clamp_unit(box.width / page.image_width_px) * 100
    height = _clamp_unit(box.height / page.image_height_px) * 100
    fill = _SEVERITY_COLOR.get(box.severity, _SEVERITY_COLOR["info"])
    border = _BORDER_COLOR.get(box.severity, _BORDER_COLOR["info"])
    title = f"{box.rule_id}" + (f" — {box.target_selector}" if box.target_selector else "")
    return (
        f'<div class="a11y-heatmap-box" '
        f'data-rule="{escape(box.rule_id)}" '
        f'data-severity="{escape(box.severity)}" '
        f'data-index="{index}" '
        f'style="left:{left:.2f}%;top:{top:.2f}%;'
        f"width:{width:.2f}%;height:{height:.2f}%;"
        f'background-color:{fill};border-color:{border};" '
        f'title="{escape(title)}"></div>'
    )


def render_heatmap_html(page: HeatmapPage) -> str:
    """Return a self-contained HTML fragment with the overlay."""

    if not page.boxes:
        return ""
    # Sort by area descending so smaller boxes paint on top — and keep
    # the response bounded.
    boxes = sorted(page.boxes, key=lambda b: -b.area)[:_MAX_BOXES_PER_PAGE]
    boxes_html = "".join(_render_box(box, page, idx) for idx, box in enumerate(boxes))
    return (
        '<figure class="a11y-heatmap">'
        f'<img class="a11y-heatmap-screenshot" src="{escape(page.screenshot_path)}" '
        f'alt="Page under audit" width="{page.image_width_px}" '
        f'height="{page.image_height_px}">'
        f'<div class="a11y-heatmap-overlay">{boxes_html}</div>'
        f"{_legend_html(boxes)}"
        "</figure>"
    )


def render_heatmap_css() -> str:
    """Return the inline CSS the reporter ships with the fragment."""

    return (
        ".a11y-heatmap{position:relative;display:inline-block;max-width:100%;}"
        ".a11y-heatmap-screenshot{display:block;width:100%;height:auto;}"
        ".a11y-heatmap-overlay{position:absolute;inset:0;}"
        ".a11y-heatmap-box{position:absolute;border:1.5px solid transparent;"
        "border-radius:2px;pointer-events:auto;cursor:help;}"
        ".a11y-heatmap-box:hover{outline:2px solid #1f2937;}"
        ".a11y-heatmap-legend{display:flex;gap:.75rem;flex-wrap:wrap;"
        "margin-top:.5rem;font-size:.85rem;}"
        ".a11y-heatmap-legend-item{display:inline-flex;align-items:center;gap:.35rem;}"
        ".a11y-heatmap-legend-swatch{display:inline-block;width:.9rem;height:.9rem;"
        "border-radius:2px;border:1px solid #d1d5db;}"
    )


def _legend_html(boxes: list[HeatmapBox]) -> str:
    severities = sorted({b.severity for b in boxes})
    if not severities:
        return ""
    swatches = "".join(
        '<span class="a11y-heatmap-legend-item">'
        f'<span class="a11y-heatmap-legend-swatch" '
        f'style="background:{_SEVERITY_COLOR.get(sev, _SEVERITY_COLOR["info"])};'
        f'border-color:{_BORDER_COLOR.get(sev, _BORDER_COLOR["info"])};"></span>'
        f"{escape(sev)}</span>"
        for sev in severities
    )
    return f'<figcaption class="a11y-heatmap-legend">{swatches}</figcaption>'


def boxes_from_axe_payload(
    payload: dict[str, Any], *, severity_by_rule: dict[str, SeverityKind] | None = None
) -> tuple[HeatmapBox, ...]:
    """Convert an axe-core JSON payload + bounding boxes into heatmap inputs.

    Expected shape:

    .. code-block:: json

        {
          "violations": [
            {
              "id": "color-contrast",
              "impact": "serious",
              "nodes": [
                {"target": ["#login"], "bbox": {"x": 12, "y": 50, "width": 100, "height": 40}}
              ]
            }
          ]
        }

    Nodes without a ``bbox`` are skipped — they would render as
    zero-area overlays.
    """

    severity_map = severity_by_rule or {}
    out: list[HeatmapBox] = []
    for violation in payload.get("violations") or []:
        if not isinstance(violation, dict):
            continue
        rule_id = str(violation.get("id", ""))
        if not rule_id:
            continue
        severity = severity_map.get(rule_id) or _impact_to_severity(
            str(violation.get("impact", ""))
        )
        for node in violation.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            bbox = node.get("bbox")
            if not isinstance(bbox, dict):
                continue
            try:
                x = float(bbox["x"])
                y = float(bbox["y"])
                width = float(bbox["width"])
                height = float(bbox["height"])
            except (KeyError, TypeError, ValueError):
                continue
            if width <= 0 or height <= 0:
                continue
            target = node.get("target") or []
            selector = ",".join(str(t) for t in target if isinstance(t, str))
            out.append(
                HeatmapBox(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    rule_id=rule_id,
                    severity=severity,
                    target_selector=selector,
                )
            )
    return tuple(out)


def _impact_to_severity(impact: str) -> SeverityKind:
    lowered = impact.lower()
    if lowered == "critical":
        return "critical"
    if lowered == "serious":
        return "high"
    if lowered == "moderate":
        return "medium"
    if lowered == "minor":
        return "low"
    return "info"


__all__ = [
    "HeatmapBox",
    "HeatmapPage",
    "SeverityKind",
    "boxes_from_axe_payload",
    "render_heatmap_css",
    "render_heatmap_html",
]
