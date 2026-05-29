"""Integration tests for the loading / error-state check (task 19.10)."""

from __future__ import annotations

from modules.llm_audit.checks.loading_error_states import check_loading_error_states
from modules.llm_audit.models import LoadingErrorObservation


def _obs(**overrides: object) -> LoadingErrorObservation:
    base = {
        "route_url": "http://localhost:3000/dashboard",
        "probed_endpoint": "/api/orders",
        "delay_ms": 0,
        "forced_status": None,
        "showed_loading_indicator": False,
        "showed_error_state": False,
        "ui_reported_success": False,
    }
    base.update(overrides)
    return LoadingErrorObservation(**base)  # type: ignore[arg-type]


def test_delayed_call_with_loading_indicator_is_clean() -> None:
    obs = _obs(delay_ms=1500, showed_loading_indicator=True)
    assert check_loading_error_states([obs]) == ()


def test_delayed_call_without_loading_indicator_is_flagged() -> None:
    obs = _obs(delay_ms=1500, showed_loading_indicator=False)
    findings = check_loading_error_states([obs])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-NO-LOADING-STATE"


def test_500_with_error_state_is_clean() -> None:
    obs = _obs(forced_status=500, showed_error_state=True)
    assert check_loading_error_states([obs]) == ()


def test_500_without_error_state_is_flagged() -> None:
    obs = _obs(forced_status=500, showed_error_state=False)
    findings = check_loading_error_states([obs])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-NO-ERROR-STATE"


def test_500_with_ui_success_is_high() -> None:
    obs = _obs(forced_status=500, showed_error_state=False, ui_reported_success=True)
    findings = check_loading_error_states([obs])
    assert len(findings) == 1
    assert findings[0].severity_override == "high"
