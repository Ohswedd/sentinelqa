"""Unit tests for :mod:`modules.security.checks.bundle_secrets` (task 32.07)."""

from __future__ import annotations

from modules.security.checks.bundle_secrets import (
    PATTERNS,
    evaluate_bundle_scan,
    scan_bundle_text,
)


def _ids(issues):
    return {i.rule_id for i in issues}


def test_aws_pattern_matches() -> None:
    text = 'const k = "AKIAIOSFODNN7EXAMPLE"; foo();'
    result = scan_bundle_text("https://app.example/static/main.js", text)
    rules = {rid for rid, _ in result.matches}
    assert "SEC-BUNDLE-SECRET-AWS" in rules


def test_stripe_live_key_matches() -> None:
    text = "stripe.setKey('sk_live_4eC39HqLyjWDarjtT1zdp7dc');"
    result = scan_bundle_text("https://app.example/main.js", text)
    rules = {rid for rid, _ in result.matches}
    assert "SEC-BUNDLE-SECRET-STRIPE" in rules


def test_github_token_matches() -> None:
    text = "const t='ghp_ABCdefGHIjklMNOpqrSTUvwxYZ0123456789';"
    result = scan_bundle_text("https://app.example/main.js", text)
    rules = {rid for rid, _ in result.matches}
    assert "SEC-BUNDLE-SECRET-GITHUB" in rules


def test_pem_private_key_matches() -> None:
    text = "-----BEGIN PRIVATE KEY-----\nMIIE..."
    result = scan_bundle_text("https://app.example/main.js", text)
    rules = {rid for rid, _ in result.matches}
    assert "SEC-BUNDLE-SECRET-PRIVATE-KEY" in rules


def test_clean_bundle_emits_no_findings() -> None:
    text = "var add = (a, b) => a + b;"
    result = scan_bundle_text("https://app.example/main.js", text)
    assert result.matches == ()
    assert list(evaluate_bundle_scan(result)) == []


def test_evaluate_carries_cwe_and_redacted_prefix() -> None:
    text = 'const k = "AKIAIOSFODNN7EXAMPLE";'
    result = scan_bundle_text("https://app.example/main.js", text)
    issues = list(evaluate_bundle_scan(result))
    assert issues
    issue = issues[0]
    assert issue.evidence.get("cwe_id") == "CWE-540"
    prefix = str(issue.evidence.get("match_prefix") or "")
    assert prefix and prefix.endswith("…")
    assert "AKIAIOSFODNN7EXAMPLE" not in (issue.title + issue.description + str(issue.evidence))


def test_truncated_flag_propagates_into_evidence() -> None:
    text = 'const k = "AKIAIOSFODNN7EXAMPLE";'
    result = scan_bundle_text("https://app.example/main.js", text, truncated=True)
    issues = list(evaluate_bundle_scan(result))
    assert issues[0].evidence.get("truncated") == "true"


def test_pattern_set_is_fixed() -> None:
    # Drift here means the safety guard's claim about the credential
    # detector being a fixed list breaks.
    assert len(PATTERNS) == 7
