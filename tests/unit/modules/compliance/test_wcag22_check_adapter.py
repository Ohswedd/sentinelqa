"""Phase 34.05 — compliance-module-side WCAG 2.2 adapter."""

from __future__ import annotations

import json
from pathlib import Path

from modules.compliance.wcag22_check import load_wcag22_signals, run_wcag22_check


def _write_signals(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "wcag22.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_signals_missing_returns_signals_seen_false(tmp_path: Path) -> None:
    report = run_wcag22_check(tmp_path / "nope.json")
    assert report.signals_seen is False
    assert report.issues == ()


def test_signals_path_is_none_returns_empty_report() -> None:
    report = run_wcag22_check(None)
    assert report.signals_seen is False
    assert report.issues == ()


def test_load_wcag22_signals_returns_none_for_missing(tmp_path: Path) -> None:
    assert load_wcag22_signals(tmp_path / "nope.json") is None


def test_load_wcag22_signals_returns_none_for_non_dict(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_wcag22_signals(path) is None


def test_load_wcag22_signals_returns_none_for_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_wcag22_signals(path) is None


def test_focus_obscured_fires_via_adapter(tmp_path: Path) -> None:
    payload = {
        "route": "/login",
        "focusables": [
            {"selector": "#email", "box": {"x": 20, "y": 50, "width": 300, "height": 32}}
        ],
        "sticky_overlays": [
            {
                "selector": "header.sticky",
                "box": {"x": 0, "y": 0, "width": 1280, "height": 80},
                "position": "sticky",
            }
        ],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert report.signals_seen is True
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.category == "focus-obscured"
    assert issue.success_criterion == "2.4.11"
    assert issue.route == "/login"
    assert issue.compliance_id == "wcag-2.2:focus-not-obscured-min"


def test_target_size_fires_via_adapter(tmp_path: Path) -> None:
    payload = {
        "clickables": [
            {
                "selector": "button.icon",
                "box": {"x": 10, "y": 10, "width": 20, "height": 20},
                "tag": "button",
            }
        ],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert len(report.issues) == 1
    assert report.issues[0].category == "target-size-min"
    assert report.issues[0].compliance_id == "wcag-2.2:target-size-min"


def test_dragging_movements_fires_via_adapter(tmp_path: Path) -> None:
    payload = {
        "draggables": [{"selector": "#row", "draggable_attr": True}],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert len(report.issues) == 1
    assert report.issues[0].category == "dragging-movements"


def test_redundant_entry_fires_via_adapter(tmp_path: Path) -> None:
    payload = {
        "form_fields": [
            {"selector": "#a", "step": 1, "name": "email", "purpose": "email"},
            {"selector": "#b", "step": 2, "name": "email_confirm", "purpose": "email"},
        ],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert len(report.issues) == 1
    assert report.issues[0].category == "redundant-entry"


def test_accessible_authentication_fires_via_adapter(tmp_path: Path) -> None:
    payload = {
        "auth_challenges": [
            {"selector": "#captcha", "kind": "image-captcha", "has_alternative": False}
        ],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert len(report.issues) == 1
    assert report.issues[0].category == "accessible-authentication"


def test_adapter_skips_malformed_entries(tmp_path: Path) -> None:
    payload = {
        "focusables": ["not a dict", {"selector": 123}, {}],
        "sticky_overlays": [None],
        "clickables": [{"selector": None}],
        "draggables": [{}],
        "form_fields": [{"selector": "x"}, {"step": "not a number", "selector": "y"}],
        "auth_challenges": [{}],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert report.signals_seen is True
    assert report.issues == ()


def test_adapter_normalises_invalid_position(tmp_path: Path) -> None:
    payload = {
        "focusables": [
            {"selector": "#email", "box": {"x": 20, "y": 50, "width": 300, "height": 32}}
        ],
        "sticky_overlays": [
            {
                "selector": "header.sticky",
                "box": {"x": 0, "y": 0, "width": 1280, "height": 80},
                "position": "wrong",
            }
        ],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    # Position 'wrong' is normalised to 'sticky'; overlap still detected.
    assert len(report.issues) == 1


def test_adapter_defaults_route_to_slash(tmp_path: Path) -> None:
    payload = {
        "clickables": [
            {"selector": "button", "box": {"x": 0, "y": 0, "width": 10, "height": 10}},
        ],
    }
    path = _write_signals(tmp_path, payload)
    report = run_wcag22_check(path)
    assert report.issues[0].route == "/"
