"""Unit tests for :mod:`modules.security.checks.jwt_weakness`."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import pytest

from modules.security.checks.jwt_weakness import (
    WEAK_HS256_SECRETS,
    decode_jwt,
    evaluate_jwt,
    scan_observations,
)


def _b64url(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _make_jwt(header: dict[str, Any], payload: dict[str, Any], secret: str | None = None) -> str:
    h = _b64url(json.dumps(header, sort_keys=True).encode("utf-8"))
    p = _b64url(json.dumps(payload, sort_keys=True).encode("utf-8"))
    if secret is None:
        sig = ""
    else:
        signature = hmac.new(
            secret.encode("utf-8"),
            f"{h}.{p}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        sig = _b64url(signature)
    return f"{h}.{p}.{sig}"


def test_decode_jwt_returns_none_on_garbage() -> None:
    assert decode_jwt("not-a-jwt") is None
    assert decode_jwt("a.b.c") is None
    assert decode_jwt("eyJ.eyJ.eyJ") is None


def test_alg_none_is_critical() -> None:
    token = _make_jwt({"alg": "none", "typ": "JWT"}, {"sub": "alice"})
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    assert any(i.rule_id == "SEC-JWT-ALG-NONE" for i in issues)
    rule = next(i for i in issues if i.rule_id == "SEC-JWT-ALG-NONE")
    assert rule.severity == "critical"
    assert rule.evidence.get("cwe_id") == "CWE-347"


def test_weak_hs256_secret_matches_one_in_wordlist() -> None:
    token = _make_jwt(
        {"alg": "HS256", "typ": "JWT"},
        {"sub": "alice", "exp": int(time.time()) + 3600},
        secret="secret",
    )
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    assert any(i.rule_id == "SEC-JWT-WEAK-HS256-SECRET" for i in issues)


def test_strong_hs256_secret_is_clean() -> None:
    token = _make_jwt(
        {"alg": "HS256", "typ": "JWT"},
        {"sub": "alice", "exp": int(time.time()) + 3600},
        secret="UB3yEx5K1q4z7s8tF9mNcQyD9Yp0kLmAj2vR8oX1pT0",
    )
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    assert not any(i.rule_id == "SEC-JWT-WEAK-HS256-SECRET" for i in issues)


def test_missing_exp_flagged_as_medium() -> None:
    token = _make_jwt({"alg": "HS256"}, {"sub": "alice"}, secret="rotated-strong-secret-XYZ")
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    missing_exp = next(i for i in issues if i.rule_id == "SEC-JWT-MISSING-EXP")
    assert missing_exp.severity == "medium"


def test_expired_token_flagged() -> None:
    token = _make_jwt(
        {"alg": "HS256"},
        {"sub": "alice", "exp": 1_000_000},  # 2001
        secret="rotated-strong-secret-XYZ",
    )
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    assert any(i.rule_id == "SEC-JWT-EXPIRED" for i in issues)


def test_missing_iss_aud_for_multi_tenant_token() -> None:
    token = _make_jwt(
        {"alg": "HS256"},
        {
            "sub": "alice",
            "tenant_id": "acme",
            "exp": int(time.time()) + 3600,
        },
        secret="rotated-strong-secret-XYZ",
    )
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    iss = next(i for i in issues if i.rule_id == "SEC-JWT-MISSING-ISS-AUD")
    missing = str(iss.evidence.get("missing_claims") or "")
    assert "aud" in missing


def test_redacted_prefix_never_logs_full_token() -> None:
    token = _make_jwt({"alg": "none"}, {"sub": "alice"})
    decoded = decode_jwt(token)
    assert decoded is not None
    issues = list(evaluate_jwt(decoded, location="header:authorization", now=time.time()))
    prefix = issues[0].evidence.get("token_prefix") or ""
    assert isinstance(prefix, str)
    assert len(prefix) <= 10
    assert token not in str(issues)


def test_scan_observations_walks_full_value() -> None:
    token = _make_jwt({"alg": "none"}, {"sub": "alice"})
    obs = [("header:authorization", f"Bearer {token}")]
    issues = list(scan_observations(obs, now=time.time()))
    assert any(i.rule_id == "SEC-JWT-ALG-NONE" for i in issues)


def test_weak_hs256_wordlist_is_fixed_size() -> None:
    # CLAUDE §6: the candidate set must be a small enumerated list, not a
    # brute-force dictionary. This is a load-bearing assertion.
    assert len(WEAK_HS256_SECRETS) <= 8


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "Bearer eyJ.bad",
        "junk: eyJabc.def.ghi",
    ],
)
def test_scan_observations_ignores_non_jwt(garbage: str) -> None:
    issues = list(scan_observations([("header:authorization", garbage)], now=time.time()))
    assert issues == []
