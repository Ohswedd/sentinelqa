"""Integration tests for the console-errors check."""

from __future__ import annotations

from modules.llm_audit.checks.console_errors import check_console_errors
from modules.llm_audit.models import ConsoleEntry


def _entry(**overrides: object) -> ConsoleEntry:
    base = {
        "route_url": "http://localhost:3000/dashboard",
        "level": "error",
        "text": "TypeError: cannot read property of undefined",
        "ui_reported_success": False,
    }
    base.update(overrides)
    return ConsoleEntry(**base)  # type: ignore[arg-type]


def test_error_with_ui_success_is_flagged() -> None:
    findings = check_console_errors([_entry(ui_reported_success=True)])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-CONSOLE-ERROR-IGNORED"


def test_error_without_ui_success_is_silent() -> None:
    assert check_console_errors([_entry(ui_reported_success=False)]) == ()


def test_log_level_is_silent() -> None:
    assert check_console_errors([_entry(level="log", ui_reported_success=True)]) == ()


def test_unhandled_rejection_is_flagged() -> None:
    entry = _entry(is_unhandled_rejection=True, level="error")
    findings = check_console_errors([entry])
    assert any(f.rule_id == "LLM-UNHANDLED-PROMISE" for f in findings)


def test_third_party_host_filtered_out() -> None:
    entry = _entry(
        ui_reported_success=True,
        source_url="https://www.google-analytics.com/collect",
    )
    findings = check_console_errors([entry], third_party_hosts=["google-analytics.com"])
    assert findings == ()


def test_unhandled_rejection_third_party_filtered_out() -> None:
    entry = _entry(
        is_unhandled_rejection=True,
        source_url="https://analytics.ads.example.com/beacon",
    )
    findings = check_console_errors([entry], third_party_hosts=["ads.example.com"])
    assert findings == ()


def test_one_error_per_route() -> None:
    findings = check_console_errors(
        [
            _entry(ui_reported_success=True, text="error A"),
            _entry(ui_reported_success=True, text="error B"),
        ],
    )
    # Both have the same route — we collapse to one finding per route.
    assert len(findings) == 1
