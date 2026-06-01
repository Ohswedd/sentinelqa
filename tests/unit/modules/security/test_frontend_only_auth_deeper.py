"""Unit tests for :mod:`modules.security.checks.frontend_only_auth_deeper`."""

from __future__ import annotations

from modules.security.checks.frontend_only_auth_deeper import (
    ObservedEndpoint,
    ProbeOutcome,
    classify_endpoint,
    evaluate_outcome,
    looks_public,
)


def _endpoint(url: str = "https://api.example/users/me") -> ObservedEndpoint:
    return ObservedEndpoint(
        method="GET",
        url=url,
        saw_payload_when_authenticated=True,
    )


def test_looks_public_recognises_health_and_public_paths() -> None:
    assert looks_public("https://api.example/api/public/feed")
    assert looks_public("https://api.example/api/health")
    assert not looks_public("https://api.example/api/users/me")


def test_classify_apparently_public() -> None:
    ep = _endpoint("https://api.example/api/public/feed")
    assert (
        classify_endpoint(ep, anonymous_status=200, anonymous_body_bytes=12) == "apparently_public"
    )


def test_classify_gated_correctly_when_401() -> None:
    ep = _endpoint()
    assert classify_endpoint(ep, anonymous_status=401, anonymous_body_bytes=0) == "gated_correctly"


def test_classify_broken_when_anonymous_200_with_body() -> None:
    ep = _endpoint()
    assert classify_endpoint(ep, anonymous_status=200, anonymous_body_bytes=512) == "broken"


def test_classify_gated_when_200_empty_body() -> None:
    ep = _endpoint()
    # 200 with empty body is ambiguous; we treat it as gated rather than
    # broken because there's no leaked payload.
    assert classify_endpoint(ep, anonymous_status=200, anonymous_body_bytes=0) == "gated_correctly"


def test_evaluate_outcome_emits_finding_for_broken() -> None:
    outcome = ProbeOutcome(
        endpoint=_endpoint(),
        classification="broken",
        anonymous_status=200,
        anonymous_body_bytes=1024,
    )
    issues = list(evaluate_outcome(outcome))
    assert issues
    assert issues[0].evidence.get("owasp_api_id") == "API-2023-01"


def test_evaluate_outcome_emits_nothing_for_gated() -> None:
    outcome = ProbeOutcome(
        endpoint=_endpoint(),
        classification="gated_correctly",
        anonymous_status=401,
        anonymous_body_bytes=0,
    )
    assert list(evaluate_outcome(outcome)) == []
