"""Integration tests for the dead-button check."""

from __future__ import annotations

from modules.llm_audit.checks.dead_buttons import check_dead_buttons
from modules.llm_audit.models import ButtonObservation


def _btn(**overrides: object) -> ButtonObservation:
    base = {
        "route_url": "http://localhost:3000/dashboard",
        "selector": "button.save",
        "label": "Save",
    }
    base.update(overrides)
    return ButtonObservation(**base)  # type: ignore[arg-type]


def test_button_with_static_handler_is_not_flagged() -> None:
    button = _btn(has_static_handler=True)
    assert check_dead_buttons([button]) == ()


def test_disabled_button_is_not_flagged() -> None:
    assert check_dead_buttons([_btn(disabled=True)]) == ()


def test_decorative_button_is_not_flagged() -> None:
    assert check_dead_buttons([_btn(is_decorative=True)]) == ()


def test_disclosure_button_is_not_flagged() -> None:
    assert check_dead_buttons([_btn(is_disclosure=True)]) == ()


def test_runtime_silent_button_without_static_handler_is_flagged() -> None:
    button = _btn(
        observed_network_within_2s=False,
        observed_navigation=False,
        observed_console_error=False,
        observed_dom_change=False,
    )
    findings = check_dead_buttons([button])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-DEAD-BTN"
    assert findings[0].confidence_override == 0.9


def test_button_with_runtime_effect_is_not_flagged() -> None:
    # The button has no static handler but produced a network call.
    button = _btn(observed_network_within_2s=True)
    assert check_dead_buttons([button]) == ()


def test_no_runtime_signal_lowers_confidence() -> None:
    button = _btn()
    findings = check_dead_buttons([button])
    assert len(findings) == 1
    assert findings[0].confidence_override == 0.55
