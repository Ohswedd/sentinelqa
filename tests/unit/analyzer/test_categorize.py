"""Categorization rule tests."""

from __future__ import annotations

from engine.analyzer.categorize import categorize, categorize_module_error
from engine.analyzer.models import AttemptOutcome, NetworkRecord

from tests.unit.analyzer.conftest import make_signal


def test_flake_pass_on_retry():
    signal = make_signal(
        status="flaky",
        retries=1,
        attempts=(
            AttemptOutcome(attempt=0, status="failed", duration_ms=900, error_message="timeout"),
            AttemptOutcome(attempt=1, status="passed", duration_ms=850),
        ),
        network=(
            NetworkRecord(
                url="https://example.test/", method="GET", status_code=200, duration_ms=12
            ),
        ),
    )
    out = categorize(signal)
    assert out.category == "flake"
    assert out.confidence > 0.8


def test_flake_alternating_attempts():
    signal = make_signal(
        status="failed",
        retries=2,
        attempts=(
            AttemptOutcome(attempt=0, status="passed", duration_ms=100),
            AttemptOutcome(attempt=1, status="failed", duration_ms=120, error_message="boom"),
        ),
    )
    out = categorize(signal)
    assert out.category == "flake"


def test_environment_failure_on_browser_crash():
    signal = make_signal(
        error_name="TargetClosedError",
        error_message="Target closed: browser has been closed",
    )
    out = categorize(signal)
    assert out.category == "environment_failure"
    assert out.confidence >= 0.85


def test_environment_failure_on_port_conflict():
    signal = make_signal(error_message="listen EADDRINUSE: address already in use 0.0.0.0:8080")
    out = categorize(signal)
    assert out.category == "environment_failure"


def test_environment_failure_on_navigation_timeout_without_response():
    signal = make_signal(
        error_name="TimeoutError",
        error_message="page.goto: Timeout 30000ms exceeded waiting for navigation",
        network=(),
    )
    out = categorize(signal)
    assert out.category == "environment_failure"


def test_app_bug_on_5xx():
    signal = make_signal(
        error_message="expect(received).toBeVisible() failed",
        network=(
            NetworkRecord(
                url="https://example.test/api/users", method="GET", status_code=503, duration_ms=412
            ),
        ),
    )
    out = categorize(signal)
    assert out.category == "app_bug"
    assert out.confidence > 0.9


def test_test_bug_on_locator_timeout_with_healthy_app():
    signal = make_signal(
        error_message=(
            "locator.click: Timeout 30000ms exceeded. "
            "Waiting for selector 'button[name=\"Sign in\"]'"
        ),
        network=(
            NetworkRecord(
                url="https://example.test/", method="GET", status_code=200, duration_ms=10
            ),
        ),
    )
    out = categorize(signal)
    assert out.category == "test_bug"


def test_test_bug_uncertain_when_no_network():
    signal = make_signal(
        error_message="locator.click: Timeout 30000ms exceeded waiting for selector",
        network=(),
    )
    out = categorize(signal)
    assert out.category == "test_bug"
    assert out.confidence < 0.7


def test_auth_failure_on_401():
    signal = make_signal(
        error_message="expect(page).toHaveURL failed",
        network=(
            NetworkRecord(
                url="https://example.test/api/me", method="GET", status_code=401, duration_ms=22
            ),
        ),
    )
    out = categorize(signal)
    assert out.category == "auth_failure"


def test_auth_failure_from_fixture():
    signal = make_signal(
        fixture_failed=True,
        error_message="login failed; invalid credentials",
    )
    out = categorize(signal)
    assert out.category == "auth_failure"


def test_data_setup_failure_from_fixture():
    signal = make_signal(
        title="checkout cart loads",  # avoid the default "sign in" title
        fixture_failed=True,
        error_message="failed to seed the catalog",
    )
    out = categorize(signal)
    assert out.category == "data_setup_failure"


def test_api_failure_on_422():
    signal = make_signal(
        error_message="API contract assertion failed",
        network=(
            NetworkRecord(
                url="https://example.test/api/orders",
                method="POST",
                status_code=422,
                duration_ms=44,
            ),
        ),
    )
    out = categorize(signal)
    assert out.category == "api_failure"


def test_accessibility_violation_from_a11y_module():
    signal = make_signal(module="a11y")
    out = categorize(signal)
    assert out.category == "accessibility_violation"


def test_accessibility_violation_from_axe_message_in_non_a11y_module():
    signal = make_signal(
        module="functional",
        error_message="axe violation: color-contrast",
    )
    out = categorize(signal)
    assert out.category == "accessibility_violation"


def test_security_finding_from_security_module():
    signal = make_signal(module="security")
    out = categorize(signal)
    assert out.category == "security_finding"


def test_performance_regression_from_performance_module():
    signal = make_signal(module="performance")
    out = categorize(signal)
    assert out.category == "performance_regression"


def test_performance_regression_from_budget_message():
    signal = make_signal(error_message="LCP budget exceeded: 3400ms > 2500ms")
    out = categorize(signal)
    assert out.category == "performance_regression"


def test_data_setup_failure_from_seed_keyword():
    signal = make_signal(
        title="checkout cart",  # avoid the default sign-in title that triggers auth heuristics
        error_message="failed to load test data fixture for catalog",
    )
    out = categorize(signal)
    assert out.category == "data_setup_failure"


def test_unknown_when_no_rule_matches():
    signal = make_signal(error_message="completely novel and unhelpful message")
    out = categorize(signal)
    assert out.category == "unknown"
    assert out.confidence <= 0.5
    assert "novel" in out.rationale.lower() or "no rule" in out.rationale.lower()


def test_secondary_categories_are_preserved():
    # Both a 5xx (app_bug) and an axe-style message (accessibility): app_bug should win
    # but accessibility appears as secondary.
    signal = make_signal(
        error_message="axe violation: focus order",
        network=(
            NetworkRecord(
                url="https://example.test/api", method="GET", status_code=500, duration_ms=10
            ),
        ),
    )
    out = categorize(signal)
    assert out.category == "app_bug"
    assert any(cat == "accessibility_violation" for cat, _ in out.secondary)


# ---------------------------------------------------------------------------
# Module-error categorization
# ---------------------------------------------------------------------------


def test_module_error_import_is_environment():
    out = categorize_module_error(
        module="functional", exc_type="ModuleNotFoundError", exc_message="no module named foo"
    )
    assert out.category == "environment_failure"
    assert out.confidence >= 0.85


def test_module_error_network_is_environment():
    out = categorize_module_error(
        module="api", exc_type="ConnectionRefusedError", exc_message="refused"
    )
    assert out.category == "environment_failure"


def test_module_error_unsafe_is_environment():
    out = categorize_module_error(
        module="security", exc_type="UnsafeTargetError", exc_message="blocked"
    )
    assert out.category == "environment_failure"
    assert out.confidence >= 0.9


def test_module_error_test_execution_is_test_bug():
    out = categorize_module_error(
        module="functional",
        exc_type="TestExecutionError",
        exc_message="suite failed",
    )
    assert out.category == "test_bug"


def test_module_error_config_error_is_environment():
    out = categorize_module_error(module="discovery", exc_type="ConfigError", exc_message="invalid")
    assert out.category == "environment_failure"


def test_module_error_default_is_low_confidence_environment():
    out = categorize_module_error(
        module="functional", exc_type="NovelError", exc_message="something else"
    )
    assert out.category == "environment_failure"
    assert out.confidence < 0.6


def test_module_error_unsafe_via_message_match():
    out = categorize_module_error(
        module="security", exc_type="RuntimeError", exc_message="unsafe operation"
    )
    assert out.category == "environment_failure"


def test_module_error_empty_exc_type_does_not_crash():
    out = categorize_module_error(module="functional", exc_type="", exc_message="")
    assert out.category == "environment_failure"
    assert out.confidence < 0.6
