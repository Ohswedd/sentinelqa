"""Retry / quarantine decision tests."""

from __future__ import annotations

from engine.analyzer.categorize import categorize
from engine.analyzer.models import FailureClassification, FailureSignal, NetworkRecord
from engine.analyzer.retry_decision import FailureHistory, should_retry

from tests.unit.analyzer.conftest import make_signal


def _classify(signal: FailureSignal) -> FailureClassification:
    return categorize(signal)


def test_flake_recommends_retry():
    signal = make_signal(status="flaky", retries=1)
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "retry"


def test_environment_failure_recommends_retry():
    signal = make_signal(error_name="TargetClosedError", error_message="Target closed")
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "retry"


def test_app_bug_no_retry():
    signal = make_signal(
        network=(NetworkRecord(url="https://x", method="GET", status_code=500, duration_ms=1),),
    )
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_api_failure_no_retry():
    signal = make_signal(
        network=(
            NetworkRecord(url="https://x/api", method="POST", status_code=422, duration_ms=1),
        ),
    )
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_security_no_retry():
    signal = make_signal(module="security")
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_a11y_no_retry():
    signal = make_signal(module="a11y")
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_performance_no_retry():
    signal = make_signal(module="performance")
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_auth_failure_in_fixture_no_retry():
    signal = make_signal(fixture_failed=True, error_message="login failed")
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_auth_failure_mid_test_recommends_retry():
    # 401 surfaced mid-test (session timeout vs deny is worth distinguishing).
    signal = make_signal(
        network=(
            NetworkRecord(url="https://x/api/me", method="GET", status_code=401, duration_ms=1),
        ),
    )
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "retry"


def test_test_bug_quarantine_candidate_when_retried_already():
    signal = make_signal(
        retries=1,
        error_message="locator.click: Timeout 30000ms exceeded waiting for selector",
        network=(NetworkRecord(url="https://x/", method="GET", status_code=200, duration_ms=1),),
    )
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "quarantine_candidate"


def test_test_bug_no_action_when_first_attempt():
    signal = make_signal(
        retries=0,
        error_message="locator.click: Timeout 30000ms exceeded waiting for selector",
        network=(NetworkRecord(url="https://x/", method="GET", status_code=200, duration_ms=1),),
    )
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_test_bug_quarantine_when_history_recurring():
    signal = make_signal(
        retries=0,
        error_message="locator.click: Timeout 30000ms exceeded waiting for selector",
        network=(NetworkRecord(url="https://x/", method="GET", status_code=200, duration_ms=1),),
    )
    cls = _classify(signal)
    history = FailureHistory(total_recent_runs=5, failed_recent_runs=4, last_passed=False)
    out = should_retry(signal, cls, history=history)
    assert out.decision == "quarantine_candidate"


def test_data_setup_no_retry():
    signal = make_signal(fixture_failed=True, error_message="failed to seed catalog")
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_unknown_defaults_to_no_action():
    cls = FailureClassification(category="unknown", confidence=0.3, rationale="no match")
    signal = make_signal()
    out = should_retry(signal, cls)
    assert out.decision == "no_action"


def test_retry_cap_enforced_regardless_of_category():
    signal = make_signal(status="flaky", retries=2)
    cls = _classify(signal)
    out = should_retry(signal, cls)
    assert out.decision == "no_action"
    assert "Already retried" in out.reason
