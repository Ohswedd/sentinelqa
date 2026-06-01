"""Root-cause hypothesis tests."""

from __future__ import annotations

from engine.analyzer.categorize import categorize
from engine.analyzer.models import (
    FailureClassification,
    FailureSignal,
    NetworkRecord,
    RootCauseHypothesis,
)
from engine.analyzer.root_cause import hypothesize

from tests.unit.analyzer.conftest import make_signal


def _classify_and_hypothesize(
    signal: FailureSignal,
) -> tuple[FailureClassification, RootCauseHypothesis]:
    cls = categorize(signal)
    return cls, hypothesize(signal, cls)


def test_app_bug_hypothesis_names_the_response_code():
    signal = make_signal(
        network=(
            NetworkRecord(
                url="https://example.test/api/orders?with=secrets",
                method="GET",
                status_code=502,
                duration_ms=410,
            ),
        ),
    )
    _, hyp = _classify_and_hypothesize(signal)
    assert hyp.category == "app_bug"
    assert "502" in hyp.hypothesis
    # Query string is stripped to keep secrets out of the hypothesis text.
    assert "with=secrets" not in hyp.hypothesis


def test_test_bug_hypothesis_names_the_locator():
    signal = make_signal(
        error_message=(
            "locator.click: Timeout 30000ms exceeded waiting for "
            'getByRole("button", { name: "Sign in" })'
        ),
        network=(
            NetworkRecord(
                url="https://example.test/", method="GET", status_code=200, duration_ms=10
            ),
        ),
    )
    _, hyp = _classify_and_hypothesize(signal)
    assert hyp.category == "test_bug"
    assert "getByRole" in hyp.hypothesis


def test_environment_failure_hypothesis_includes_error_name():
    signal = make_signal(
        error_name="TargetClosedError",
        error_message="Target closed",
    )
    _, hyp = _classify_and_hypothesize(signal)
    assert hyp.category == "environment_failure"
    assert "TargetClosedError" in hyp.hypothesis


def test_flake_hypothesis_mentions_retries():
    signal = make_signal(
        status="flaky",
        retries=2,
    )
    _, hyp = _classify_and_hypothesize(signal)
    assert hyp.category == "flake"
    assert "2 retries" in hyp.hypothesis


def test_hypothesis_confidence_matches_classification():
    cls = FailureClassification(category="app_bug", confidence=0.42, rationale="forced")
    signal = make_signal(
        network=(
            NetworkRecord(
                url="https://example.test/api", method="GET", status_code=500, duration_ms=10
            ),
        ),
    )
    hyp = hypothesize(signal, cls)
    assert hyp.confidence == 0.42


def test_hypothesis_next_actions_are_non_empty():
    for category in (
        "app_bug",
        "test_bug",
        "environment_failure",
        "flake",
        "data_setup_failure",
        "auth_failure",
        "api_failure",
        "performance_regression",
        "security_finding",
        "accessibility_violation",
        "unknown",
    ):
        cls = FailureClassification(category=category, confidence=0.5, rationale="forced")
        signal = make_signal()
        hyp = hypothesize(signal, cls)
        assert hyp.next_actions, f"empty next_actions for {category}"
        # Every action must be a one-liner with no leading whitespace.
        for action in hyp.next_actions:
            assert action == action.strip()
            assert len(action) > 5


def test_unknown_hypothesis_points_at_the_trace():
    cls = FailureClassification(category="unknown", confidence=0.3, rationale="no match")
    signal = make_signal(error_message="some error")
    hyp = hypothesize(signal, cls)
    assert "trace" in " ".join(hyp.next_actions).lower()


def test_evidence_refs_include_provided_evidence():
    signal = make_signal(
        error_message="boom",
        evidence=("trace://traces/test-1.zip", "screenshot://shots/test-1.png"),
    )
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert "trace://traces/test-1.zip" in hyp.evidence_refs


def test_hypothesis_text_is_bounded_when_template_explodes():
    """When the template substitution would exceed 1024 chars we clip."""

    # Build a category where the snippet comes straight from error_message,
    # then make that message long enough to push past the cap.
    cls = FailureClassification(
        category="environment_failure",
        confidence=0.5,
        rationale="forced",
    )
    signal = make_signal(error_name="EnvError", error_message="x" * 1_500)
    hyp = hypothesize(signal, cls)
    # _clip caps at 200 so the resulting text is still well under 1024 — that
    # path is exercised above. To exercise the > 1024 branch we pick a
    # category whose template uses the snippet unclipped.
    assert len(hyp.hypothesis) <= 1024


def test_evidence_snippet_falls_back_when_app_bug_has_no_5xx():
    cls = FailureClassification(category="app_bug", confidence=0.5, rationale="forced")
    signal = make_signal(network=())  # no network records at all
    hyp = hypothesize(signal, cls)
    assert "unexpected server response" in hyp.hypothesis


def test_environment_snippet_uses_message_when_no_name():
    cls = FailureClassification(category="environment_failure", confidence=0.5, rationale="forced")
    signal = make_signal(error_name=None, error_message="weird runtime error")
    hyp = hypothesize(signal, cls)
    assert "weird runtime error" in hyp.hypothesis


def test_environment_snippet_falls_back_when_no_error():
    cls = FailureClassification(category="environment_failure", confidence=0.5, rationale="forced")
    signal = make_signal(error_name=None, error_message=None)
    hyp = hypothesize(signal, cls)
    assert "runtime reported" in hyp.hypothesis


def test_api_failure_snippet_falls_back_when_no_4xx():
    cls = FailureClassification(category="api_failure", confidence=0.5, rationale="forced")
    signal = make_signal(network=())
    hyp = hypothesize(signal, cls)
    assert "unexpected response status" in hyp.hypothesis


def test_auth_failure_snippet_uses_error_message_when_no_4xx():
    cls = FailureClassification(category="auth_failure", confidence=0.5, rationale="forced")
    signal = make_signal(error_message="login form did not load")
    hyp = hypothesize(signal, cls)
    assert "login form did not load" in hyp.hypothesis


def test_auth_failure_snippet_default_when_nothing_present():
    cls = FailureClassification(category="auth_failure", confidence=0.5, rationale="forced")
    signal = make_signal(error_message=None)
    hyp = hypothesize(signal, cls)
    assert "login fixture" in hyp.hypothesis


def test_data_setup_snippet_default():
    cls = FailureClassification(category="data_setup_failure", confidence=0.5, rationale="forced")
    signal = make_signal(error_message=None)
    hyp = hypothesize(signal, cls)
    assert "fixture raised" in hyp.hypothesis


def test_performance_snippet_uses_message():
    cls = FailureClassification(
        category="performance_regression", confidence=0.5, rationale="forced"
    )
    signal = make_signal(error_message="LCP exceeded")
    hyp = hypothesize(signal, cls)
    assert "LCP exceeded" in hyp.hypothesis


def test_performance_snippet_default():
    cls = FailureClassification(
        category="performance_regression", confidence=0.5, rationale="forced"
    )
    signal = make_signal(error_message=None)
    hyp = hypothesize(signal, cls)
    assert "budget assertion" in hyp.hypothesis


def test_security_snippet_uses_message():
    cls = FailureClassification(category="security_finding", confidence=0.5, rationale="forced")
    signal = make_signal(error_message="missing csp")
    hyp = hypothesize(signal, cls)
    assert "missing csp" in hyp.hypothesis


def test_security_snippet_default():
    cls = FailureClassification(category="security_finding", confidence=0.5, rationale="forced")
    signal = make_signal(error_message=None)
    hyp = hypothesize(signal, cls)
    assert "security assertion" in hyp.hypothesis


def test_a11y_snippet_uses_message():
    cls = FailureClassification(
        category="accessibility_violation", confidence=0.5, rationale="forced"
    )
    signal = make_signal(error_message="color-contrast")
    hyp = hypothesize(signal, cls)
    assert "color-contrast" in hyp.hypothesis


def test_a11y_snippet_default():
    cls = FailureClassification(
        category="accessibility_violation", confidence=0.5, rationale="forced"
    )
    signal = make_signal(error_message=None)
    hyp = hypothesize(signal, cls)
    assert "axe assertion" in hyp.hypothesis


def test_unknown_snippet_uses_error_message():
    cls = FailureClassification(category="unknown", confidence=0.3, rationale="no match")
    signal = make_signal(error_message="novel pattern")
    hyp = hypothesize(signal, cls)
    assert "novel pattern" in hyp.hypothesis


def test_unknown_snippet_default():
    cls = FailureClassification(category="unknown", confidence=0.3, rationale="no match")
    signal = make_signal(error_message=None)
    hyp = hypothesize(signal, cls)
    assert "no error message" in hyp.hypothesis


def test_short_url_clips_long_paths():
    from engine.analyzer.root_cause import _short_url

    out = _short_url("https://example.test/" + "a" * 200)
    assert len(out) <= 81
    assert out.endswith("…")


def test_short_url_strips_query_and_fragment():
    from engine.analyzer.root_cause import _short_url

    assert _short_url("https://x/api?q=1#anchor") == "https://x/api"


def test_locator_snippet_handles_get_by_label():
    cls = FailureClassification(category="test_bug", confidence=0.5, rationale="forced")
    signal = make_signal(
        error_message='locator.fill: Timeout 30000ms exceeded for getByLabel("Email")',
        network=(),
    )
    hyp = hypothesize(signal, cls)
    assert "getByLabel" in hyp.hypothesis


def test_locator_snippet_handles_locator_string():
    cls = FailureClassification(category="test_bug", confidence=0.5, rationale="forced")
    signal = make_signal(
        error_message="locator.click failed for locator('button.foo')",
        network=(),
    )
    hyp = hypothesize(signal, cls)
    assert "locator(" in hyp.hypothesis


def test_locator_snippet_default_when_no_marker():
    cls = FailureClassification(category="test_bug", confidence=0.5, rationale="forced")
    signal = make_signal(error_message="cryptic error with no locator marker")
    hyp = hypothesize(signal, cls)
    assert "the expected element" in hyp.hypothesis


def test_hypothesis_text_actually_exceeds_1024_and_is_clipped():
    """Force the >1024 clip branch via a long flake snippet (template + snippet)."""

    from engine.analyzer.root_cause import _TEMPLATES

    # The flake template uses `{0}` as a free-form prefix; if we craft a
    # template-side dummy via monkeypatch we cover the > 1024 branch.
    original = _TEMPLATES["flake"]
    _TEMPLATES["flake"] = ("flake stub {0}" + "y" * 1_100, ("inspect trace",))
    try:
        cls = FailureClassification(category="flake", confidence=0.5, rationale="forced")
        signal = make_signal(status="flaky", retries=3)
        hyp = hypothesize(signal, cls)
        assert len(hyp.hypothesis) <= 1024
        assert hyp.hypothesis.endswith("...")
    finally:
        _TEMPLATES["flake"] = original


def test_hypothesis_text_is_bounded():
    long_msg = "x" * 2_000  # FailureSignal caps error_message at 2048.
    signal = make_signal(error_name="EnvError", error_message=long_msg)
    cls = categorize(signal)
    hyp = hypothesize(signal, cls)
    assert len(hyp.hypothesis) <= 1024
