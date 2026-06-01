# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for CSP/SRI/HSTS strictness scoring."""

from __future__ import annotations

from modules.security.checks.header_scoring import (
    ScoringResult,
    score_csp,
    score_hsts,
    score_sri,
)

# --------------------------------------------------------------------------- #
# CSP
# --------------------------------------------------------------------------- #


def test_csp_missing_scores_zero_high_severity() -> None:
    result = score_csp(None)
    assert result.score == 0
    assert result.severity == "high"
    assert "missing" in result.reasons[0].lower()


def test_csp_strict_policy_scores_near_perfect() -> None:
    strict = (
        "default-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "report-uri /csp-report;"
    )
    result = score_csp(strict)
    assert result.score >= 95
    assert result.severity in {"info", "low"}


def test_csp_unsafe_inline_penalised() -> None:
    result = score_csp("default-src 'self' 'unsafe-inline'; object-src 'none';")
    assert result.score <= 60
    assert any("unsafe-inline" in r for r in result.reasons)


def test_csp_wildcard_source_penalised() -> None:
    result = score_csp("default-src * ;")
    assert any("wildcard" in r.lower() for r in result.reasons)


def test_csp_http_scheme_penalised() -> None:
    result = score_csp("default-src 'self' http://cdn.example.com;")
    assert any("http:" in r for r in result.reasons)


def test_csp_empty_string_treated_as_missing() -> None:
    assert score_csp("   ").score == 0


# --------------------------------------------------------------------------- #
# SRI
# --------------------------------------------------------------------------- #

_PAGE_ORIGIN = "https://app.example.com"


def test_sri_no_off_host_scripts_returns_perfect() -> None:
    html = "<!doctype html><html><head>" "<script src='/main.js'></script>" "</head></html>"
    result = score_sri(html, page_origin=_PAGE_ORIGIN)
    assert result.score == 100
    assert result.severity == "info"


def test_sri_uncovered_off_host_script_drops_score() -> None:
    html = "<head>" "<script src='https://cdn.jsdelivr.net/npm/foo.js'></script>" "</head>"
    result = score_sri(html, page_origin=_PAGE_ORIGIN)
    assert result.score == 0
    assert result.severity == "high"


def test_sri_covered_off_host_script_scores_perfect() -> None:
    html = (
        "<script "
        "src='https://cdn.jsdelivr.net/npm/foo.js' "
        "integrity='sha384-abcdef'></script>"
    )
    result = score_sri(html, page_origin=_PAGE_ORIGIN)
    assert result.score == 100


def test_sri_mixed_coverage_scores_proportionally() -> None:
    html = (
        "<script src='https://cdn.example.org/a.js' integrity='sha384-x'></script>"
        "<script src='https://cdn.example.org/b.js'></script>"
    )
    result = score_sri(html, page_origin=_PAGE_ORIGIN)
    assert result.score == 50
    assert result.severity == "medium"


def test_sri_stylesheet_link_is_scored() -> None:
    html = "<link rel='stylesheet' href='https://cdn.example.org/style.css'>"
    result = score_sri(html, page_origin=_PAGE_ORIGIN)
    assert result.score == 0


def test_sri_ignores_data_url() -> None:
    html = (
        "<script src='data:application/javascript,alert(1)'></script>"
        "<script src='/local.js'></script>"
    )
    result = score_sri(html, page_origin=_PAGE_ORIGIN)
    assert result.score == 100


def test_sri_empty_html_returns_info() -> None:
    assert score_sri("", page_origin=_PAGE_ORIGIN).score == 100


# --------------------------------------------------------------------------- #
# HSTS
# --------------------------------------------------------------------------- #


def test_hsts_missing_on_http_returns_medium_severity() -> None:
    result = score_hsts(None, is_https=False)
    assert result.score == 0
    assert result.severity == "medium"


def test_hsts_missing_on_https_returns_high_severity() -> None:
    result = score_hsts(None, is_https=True)
    assert result.score == 0
    assert result.severity == "high"


def test_hsts_full_preload_eligible_scores_perfect() -> None:
    result = score_hsts(
        "max-age=31536000; includeSubDomains; preload",
        is_https=True,
    )
    assert result.score == 100
    assert result.severity == "info"
    assert any("preload list" in r.lower() for r in result.reasons)


def test_hsts_short_max_age_penalised() -> None:
    result = score_hsts(
        "max-age=86400; includeSubDomains; preload",
        is_https=True,
    )
    assert result.score == 70


def test_hsts_missing_includesubdomains_penalised() -> None:
    result = score_hsts("max-age=31536000; preload", is_https=True)
    assert result.score == 80


def test_hsts_returns_scoring_result_type() -> None:
    result = score_hsts("max-age=31536000; includeSubDomains; preload", is_https=True)
    assert isinstance(result, ScoringResult)
    assert result.name == "hsts"
