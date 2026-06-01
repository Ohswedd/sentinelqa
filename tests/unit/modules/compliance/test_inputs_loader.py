"""compliance signals JSON loader edge cases."""

from __future__ import annotations

import json
from pathlib import Path

from modules.compliance.inputs import load_ccpa_signals, load_gdpr_signals


def test_load_gdpr_returns_empty_when_path_is_none() -> None:
    assert load_gdpr_signals(None) == ()


def test_load_gdpr_returns_empty_when_path_missing(tmp_path: Path) -> None:
    assert load_gdpr_signals(tmp_path / "nope.json") == ()


def test_load_gdpr_returns_empty_for_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_gdpr_signals(path) == ()


def test_load_gdpr_returns_empty_for_non_list_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert load_gdpr_signals(path) == ()


def test_load_gdpr_skips_malformed_entries(tmp_path: Path) -> None:
    path = tmp_path / "g.json"
    payload = [
        "not a dict",
        {"banner": {"present": True}},  # missing route
        {"route": 123},  # route not a string
        {
            "route": "/",
            "banner": {"present": True, "selector": "#consent"},
            "cookies_on_first_load": [
                {},  # missing name
                {"name": ""},  # empty name
                "not a dict",
                {"name": "_ga", "domain": "x", "essential": False},
            ],
        },
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    signals = load_gdpr_signals(path)
    assert len(signals) == 1
    page = signals[0]
    assert page.route == "/"
    assert page.banner.present is True
    assert tuple(c.name for c in page.cookies_on_first_load) == ("_ga",)


def test_load_gdpr_handles_missing_banner_block(tmp_path: Path) -> None:
    path = tmp_path / "g.json"
    payload = [{"route": "/"}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    signals = load_gdpr_signals(path)
    assert len(signals) == 1
    assert signals[0].banner.present is False


def test_load_gdpr_normalises_non_dict_banner(tmp_path: Path) -> None:
    path = tmp_path / "g.json"
    payload = [{"route": "/", "banner": "not a dict"}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    signals = load_gdpr_signals(path)
    assert len(signals) == 1


def test_load_gdpr_handles_non_list_cookies(tmp_path: Path) -> None:
    path = tmp_path / "g.json"
    payload = [{"route": "/", "cookies_on_first_load": "oops"}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    signals = load_gdpr_signals(path)
    assert len(signals) == 1
    assert signals[0].cookies_on_first_load == ()


def test_load_ccpa_returns_empty_when_path_is_none() -> None:
    assert load_ccpa_signals(None) == ()


def test_load_ccpa_returns_empty_when_path_missing(tmp_path: Path) -> None:
    assert load_ccpa_signals(tmp_path / "nope.json") == ()


def test_load_ccpa_returns_empty_for_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_ccpa_signals(path) == ()


def test_load_ccpa_returns_empty_for_non_list_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert load_ccpa_signals(path) == ()


def test_load_ccpa_skips_entries_without_route(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    payload = [
        "not a dict",
        {"link_text": "Do Not Sell"},
        {"route": 123},
        {"route": "/", "link_text": "Privacy"},
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    signals = load_ccpa_signals(path)
    assert len(signals) == 1
    assert signals[0].route == "/"
