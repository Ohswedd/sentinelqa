"""Unit tests for :mod:`modules.security.checks.ssrf_redirect` (task 32.08)."""

from __future__ import annotations

from modules.security.checks.ssrf_redirect import (
    OPEN_REDIRECT_PAYLOADS,
    SSRF_PAYLOADS,
    RedirectProbeOutcome,
    SsrfProbeOutcome,
    UrlInput,
    classify_redirect_response,
    classify_ssrf_response,
    evaluate_redirect,
    evaluate_ssrf,
)


def _input() -> UrlInput:
    return UrlInput(method="GET", url="https://api/proxy", parameter="url")


def test_classify_ssrf_400_is_clean() -> None:
    assert classify_ssrf_response(403, b"forbidden host") == "clean"


def test_classify_ssrf_200_with_data_is_suspected() -> None:
    assert classify_ssrf_response(200, b"<html>imds-token: abc</html>") == "ssrf_suspected"


def test_classify_ssrf_5xx_with_rejection_text_is_clean() -> None:
    assert classify_ssrf_response(500, b"Could not resolve URL") == "clean"


def test_classify_redirect_with_attacker_location_is_open_redirect() -> None:
    assert classify_redirect_response(302, "//attacker.example.com") == "open_redirect"


def test_classify_redirect_with_allowed_location_is_clean() -> None:
    assert classify_redirect_response(302, "/dashboard") == "clean"


def test_evaluate_ssrf_carries_cwe() -> None:
    outcome = SsrfProbeOutcome(
        input=_input(),
        payload="http://127.0.0.1/",
        status=200,
        body_excerpt="<html>...</html>",
        classification="ssrf_suspected",
    )
    issues = list(evaluate_ssrf(outcome))
    assert issues
    assert issues[0].evidence.get("cwe_id") == "CWE-918"


def test_evaluate_redirect_carries_cwe() -> None:
    outcome = RedirectProbeOutcome(
        input=_input(),
        payload="//attacker.example.com",
        status=302,
        location="//attacker.example.com",
        classification="open_redirect",
    )
    issues = list(evaluate_redirect(outcome))
    assert issues
    assert issues[0].evidence.get("cwe_id") == "CWE-601"


def test_payload_lists_are_fixed() -> None:
    # CLAUDE §6 + ADR-0044 safety boundary: fixed, enumerated set.
    assert len(SSRF_PAYLOADS) == 6
    assert len(OPEN_REDIRECT_PAYLOADS) == 2
    # No random generation hooks should appear in the module — caught
    # by the safety grep test (tests/security/test_no_offensive_checks.py).
    for payload in SSRF_PAYLOADS + OPEN_REDIRECT_PAYLOADS:
        assert isinstance(payload, str)
