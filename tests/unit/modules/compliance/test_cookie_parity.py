# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for cookie consent → behaviour parity."""

from __future__ import annotations

from modules.compliance.cookie_parity import (
    CookieRecord,
    classify_cookie,
    find_parity_violations,
    survivors_after_reject,
)


def _c(name: str, domain: str = "app.example.com") -> CookieRecord:
    return CookieRecord(name=name, domain=domain)


def test_classify_strictly_necessary() -> None:
    assert classify_cookie(_c("sessionid")).kind == "strictly_necessary"
    assert classify_cookie(_c("csrftoken")).kind == "strictly_necessary"
    assert classify_cookie(_c("locale")).kind == "strictly_necessary"


def test_classify_google_analytics() -> None:
    assert classify_cookie(_c("_ga")).kind == "analytics"
    assert classify_cookie(_c("_ga_ABCD1234")).kind == "analytics"
    assert classify_cookie(_c("_gid")).kind == "analytics"


def test_classify_facebook_pixel() -> None:
    assert classify_cookie(_c("_fbp")).kind == "marketing"
    assert classify_cookie(_c("_fbc")).kind == "marketing"


def test_classify_unknown_cookie() -> None:
    assert classify_cookie(_c("custom_pref")).kind == "unknown"


def test_survivors_after_reject_identifies_persistent_cookies() -> None:
    initial = [_c("sessionid"), _c("_ga"), _c("_fbp")]
    post = [_c("sessionid"), _c("_ga"), _c("_fbp")]  # nothing cleared
    survivors = survivors_after_reject(initial, post)
    names = {c.name for c in survivors}
    assert names == {"sessionid", "_ga", "_fbp"}


def test_survivors_skips_cleared_cookies() -> None:
    initial = [_c("sessionid"), _c("_ga")]
    post = [_c("sessionid")]
    survivors = survivors_after_reject(initial, post)
    assert {c.name for c in survivors} == {"sessionid"}


def test_find_parity_violations_skips_strictly_necessary() -> None:
    initial = [_c("sessionid"), _c("_ga"), _c("_fbp")]
    post = initial
    findings = find_parity_violations(initial, post)
    names = {f.cookie.name for f in findings}
    assert names == {"_ga", "_fbp"}


def test_find_parity_violations_severity_ladder() -> None:
    initial = [_c("_ga"), _c("_fbp"), _c("custom_pref"), _c("optimizelyEndUserId")]
    findings = find_parity_violations(initial, initial)
    by_kind = {f.classification.kind: f.severity for f in findings}
    assert by_kind["analytics"] == "medium"
    assert by_kind["marketing"] == "high"
    assert by_kind["tracking"] == "high"
    assert by_kind["unknown"] == "low"


def test_find_parity_violations_returns_compliance_id() -> None:
    initial = [_c("_ga")]
    findings = find_parity_violations(initial, initial)
    assert findings[0].compliance_id == "gdpr:Art.6"


def test_find_parity_violations_returns_empty_when_jar_cleared() -> None:
    initial = [_c("_ga"), _c("_fbp")]
    post: list[CookieRecord] = []
    assert find_parity_violations(initial, post) == ()


def test_classification_rationale_is_descriptive() -> None:
    classification = classify_cookie(_c("_ga"))
    assert "analytics" in classification.rationale.lower()
