"""WCAG 2.2 signal-driven check inside the compliance module.

The deterministic check functions live in
:mod:`modules.accessibility.checks.wcag22`. This module is the
compliance-module-side adapter: it loads optional signal files from
``<run-dir>/compliance/signals/wcag22.json`` and runs the
``detect_*`` functions against them.

Pack DSL example::

 pack:
 id: wcag-2.2-aa
 includes:
 - module: compliance
 checks: [wcag22]

When no signals are available, the check reports
``signals_seen=False`` and emits no findings (the engineering guidelines: no fake
completion).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.accessibility.checks.wcag22 import (
    AuthChallenge,
    BoundingBox,
    ClickableElement,
    DraggableElement,
    FocusableElement,
    FormField,
    StickyOverlay,
    detect_accessible_authentication,
    detect_dragging_movements,
    detect_focus_obscured,
    detect_redundant_entry,
    detect_target_size,
)
from modules.compliance.models import (
    Wcag22CheckReport,
    Wcag22Issue,
)

_COMPLIANCE_ID: dict[str, str] = {
    "focus-obscured": "wcag-2.2:focus-not-obscured-min",
    "target-size-min": "wcag-2.2:target-size-min",
    "dragging-movements": "wcag-2.2:dragging-movements",
    "redundant-entry": "wcag-2.2:redundant-entry",
    "accessible-authentication": "wcag-2.2:accessible-authentication-min",
}


def load_wcag22_signals(path: Path | None) -> dict[str, list[Any]] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _box(d: dict[str, Any]) -> BoundingBox:
    return BoundingBox(
        x=float(d.get("x", 0)),
        y=float(d.get("y", 0)),
        width=float(d.get("width", 0)),
        height=float(d.get("height", 0)),
    )


def _focusables(raw: list[Any]) -> tuple[FocusableElement, ...]:
    out: list[FocusableElement] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = entry.get("selector")
        if not isinstance(selector, str):
            continue
        out.append(FocusableElement(selector=selector, box=_box(entry.get("box", {}))))
    return tuple(out)


def _overlays(raw: list[Any]) -> tuple[StickyOverlay, ...]:
    out: list[StickyOverlay] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = entry.get("selector")
        if not isinstance(selector, str):
            continue
        position = entry.get("position", "sticky")
        if position not in ("sticky", "fixed"):
            position = "sticky"
        out.append(
            StickyOverlay(
                selector=selector,
                box=_box(entry.get("box", {})),
                position=position,
            )
        )
    return tuple(out)


def _clickables(raw: list[Any]) -> tuple[ClickableElement, ...]:
    out: list[ClickableElement] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = entry.get("selector")
        if not isinstance(selector, str):
            continue
        out.append(
            ClickableElement(
                selector=selector,
                box=_box(entry.get("box", {})),
                tag=str(entry.get("tag", ""))[:32],
                role=str(entry.get("role", ""))[:64],
                inline=bool(entry.get("inline", False)),
                user_agent_default=bool(entry.get("user_agent_default", False)),
                has_keyboard_alternative=bool(entry.get("has_keyboard_alternative", False)),
            )
        )
    return tuple(out)


def _draggables(raw: list[Any]) -> tuple[DraggableElement, ...]:
    out: list[DraggableElement] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = entry.get("selector")
        if not isinstance(selector, str):
            continue
        out.append(
            DraggableElement(
                selector=selector,
                cursor=str(entry.get("cursor", ""))[:32],
                draggable_attr=bool(entry.get("draggable_attr", False)),
                has_keyboard_alternative=bool(entry.get("has_keyboard_alternative", False)),
            )
        )
    return tuple(out)


def _form_fields(raw: list[Any]) -> tuple[FormField, ...]:
    out: list[FormField] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = entry.get("selector")
        if not isinstance(selector, str):
            continue
        try:
            step = int(entry.get("step", 0))
        except (TypeError, ValueError):
            continue
        out.append(
            FormField(
                selector=selector,
                step=step,
                name=str(entry.get("name", ""))[:128],
                label=str(entry.get("label", ""))[:256],
                autocomplete=str(entry.get("autocomplete", ""))[:64],
                purpose=str(entry.get("purpose", ""))[:64],
            )
        )
    return tuple(out)


def _auth_challenges(raw: list[Any]) -> tuple[AuthChallenge, ...]:
    out: list[AuthChallenge] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = entry.get("selector")
        if not isinstance(selector, str):
            continue
        out.append(
            AuthChallenge(
                selector=selector,
                kind=str(entry.get("kind", ""))[:64],
                has_alternative=bool(entry.get("has_alternative", False)),
            )
        )
    return tuple(out)


def run_wcag22_check(signals_path: Path | None) -> Wcag22CheckReport:
    """Run every deterministic WCAG 2.2 check against ``signals_path``."""

    payload = load_wcag22_signals(signals_path)
    if payload is None:
        return Wcag22CheckReport(signals_seen=False, issues=())

    route = str(payload.get("route", "/")) or "/"
    issues: list[Wcag22Issue] = []

    focusables = _focusables(payload.get("focusables") or [])
    overlays = _overlays(payload.get("sticky_overlays") or [])
    for det in detect_focus_obscured(focusables, overlays):
        issues.append(
            Wcag22Issue(
                category="focus-obscured",
                success_criterion="2.4.11",
                route=route,
                selector=det.selector,
                description=det.description,
                compliance_id=_COMPLIANCE_ID["focus-obscured"],
            )
        )

    clickables = _clickables(payload.get("clickables") or [])
    for det in detect_target_size(clickables):
        issues.append(
            Wcag22Issue(
                category="target-size-min",
                success_criterion="2.5.8",
                route=route,
                selector=det.selector,
                description=det.description,
                compliance_id=_COMPLIANCE_ID["target-size-min"],
            )
        )

    draggables = _draggables(payload.get("draggables") or [])
    for det in detect_dragging_movements(draggables):
        issues.append(
            Wcag22Issue(
                category="dragging-movements",
                success_criterion="2.5.7",
                route=route,
                selector=det.selector,
                description=det.description,
                compliance_id=_COMPLIANCE_ID["dragging-movements"],
            )
        )

    form_fields = _form_fields(payload.get("form_fields") or [])
    for det in detect_redundant_entry(form_fields):
        issues.append(
            Wcag22Issue(
                category="redundant-entry",
                success_criterion="3.3.7",
                route=route,
                selector=det.selector,
                description=det.description,
                compliance_id=_COMPLIANCE_ID["redundant-entry"],
            )
        )

    challenges = _auth_challenges(payload.get("auth_challenges") or [])
    for det in detect_accessible_authentication(challenges):
        issues.append(
            Wcag22Issue(
                category="accessible-authentication",
                success_criterion="3.3.8",
                route=route,
                selector=det.selector,
                description=det.description,
                compliance_id=_COMPLIANCE_ID["accessible-authentication"],
            )
        )

    return Wcag22CheckReport(signals_seen=True, issues=tuple(issues))


__all__ = ["load_wcag22_signals", "run_wcag22_check"]
