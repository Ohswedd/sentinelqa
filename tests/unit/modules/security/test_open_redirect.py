# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the open-redirect enumerator + bypass matrix."""

from __future__ import annotations

from modules.security.checks.open_redirect import (
    REDIRECT_PARAM_NAMES,
    RedirectCandidate,
    bypass_vectors,
    enumerate_redirect_params,
    evaluate_redirect_response,
)

# --------------------------------------------------------------------------- #
# Enumeration
# --------------------------------------------------------------------------- #


def test_enumerate_finds_redirect_params() -> None:
    urls = [
        "https://app.example.com/login?redirect=/dashboard",
        "https://app.example.com/oauth?return_to=/home&state=abc",
        "https://app.example.com/page?lang=en",  # not in the set
    ]
    candidates = enumerate_redirect_params(urls)
    assert len(candidates) == 2
    params = {c.parameter.lower() for c in candidates}
    assert "redirect" in params
    assert "return_to" in params


def test_enumerate_is_case_insensitive_on_param_name() -> None:
    urls = ["https://app.example.com/login?RETURN_URL=/x"]
    candidates = enumerate_redirect_params(urls)
    assert len(candidates) == 1


def test_enumerate_returns_empty_for_paramless_urls() -> None:
    assert enumerate_redirect_params(["https://app.example.com/login"]) == ()


def test_enumerate_dedups_repeated_pairs() -> None:
    urls = [
        "https://app.example.com/login?redirect=/a",
        "https://app.example.com/login?redirect=/b",
    ]
    out = enumerate_redirect_params(urls)
    pairs = {(c.url, c.parameter) for c in out}
    assert len(pairs) == 2  # urls differ → both kept
    # Same-URL repeats are deduped.
    out2 = enumerate_redirect_params([*urls, urls[0]])
    assert len(out2) == 2


def test_param_name_set_covers_real_world_examples() -> None:
    for name in ("url", "next", "return_to", "callback", "destination"):
        assert name in REDIRECT_PARAM_NAMES


# --------------------------------------------------------------------------- #
# Bypass vectors
# --------------------------------------------------------------------------- #


def test_bypass_vectors_includes_canonical_bypasses() -> None:
    vectors = bypass_vectors("app.example.com")
    joined = " ".join(vectors)
    assert "//attacker.test" in joined  # protocol-relative
    assert "@attacker.test" in joined  # @-injection
    assert "%0a" in joined  # CRLF injection
    assert "[::1]" in joined  # IPv6 loopback
    assert "3232235521" in joined  # decimal IPv4
    assert "%2F%2F" in joined  # double URL encoded


def test_bypass_vectors_substitute_trusted_host() -> None:
    vectors = bypass_vectors("specific.host.example")
    # The substitution must appear in at least one payload.
    assert any("specific.host.example" in v for v in vectors)


# --------------------------------------------------------------------------- #
# Response evaluation
# --------------------------------------------------------------------------- #


_CAND = RedirectCandidate(url="https://app.example.com/login?next=x", parameter="next")
_ALLOW = frozenset({"app.example.com", "trusted.example.com"})


def test_evaluate_returns_none_for_2xx() -> None:
    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="//attacker.test",
        response_status=200,
        location_header="",
        trusted_hosts=_ALLOW,
    )
    assert result is None


def test_evaluate_returns_none_for_redirect_to_trusted_host() -> None:
    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="//attacker.test",
        response_status=302,
        location_header="https://app.example.com/dashboard",
        trusted_hosts=_ALLOW,
    )
    assert result is None


def test_evaluate_returns_none_for_relative_redirect() -> None:
    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="//attacker.test",
        response_status=302,
        location_header="/login",
        trusted_hosts=_ALLOW,
    )
    assert result is None


def test_evaluate_flags_off_allowlist_redirect_high() -> None:
    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="//attacker.test",
        response_status=302,
        location_header="//attacker.test/landing",
        trusted_hosts=_ALLOW,
    )
    assert result is not None
    assert result.severity == "high"
    assert "Attacker-controlled payload" in result.rationale


def test_evaluate_lower_severity_when_payload_not_reflected() -> None:
    """Server picked its own off-allowlist destination — still a finding."""

    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="//attacker.test",
        response_status=302,
        location_header="https://other.example.org/x",
        trusted_hosts=_ALLOW,
    )
    assert result is not None
    assert result.severity == "medium"


def test_evaluate_handles_subdomain_in_allowlist() -> None:
    """A redirect to ``foo.app.example.com`` must be allowed when ``app.example.com`` is trusted."""

    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="https://foo.app.example.com",
        response_status=302,
        location_header="https://foo.app.example.com/path",
        trusted_hosts=_ALLOW,
    )
    assert result is None


def test_evaluate_strips_userinfo_in_location() -> None:
    """``@``-injection must not fool the allowlist check."""

    result = evaluate_redirect_response(
        candidate=_CAND,
        payload="https://app.example.com@attacker.test",
        response_status=302,
        location_header="https://app.example.com@attacker.test/path",
        trusted_hosts=_ALLOW,
    )
    assert result is not None
    assert result.severity == "high"
