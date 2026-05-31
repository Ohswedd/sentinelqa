"""Unit tests for :mod:`modules.security.checks.tls_posture` (task 32.03)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from modules.security.checks.tls_posture import (
    TlsHandshakeResult,
    _parse_hsts_max_age,
    evaluate_handshake,
)
from modules.security.models import SecurityIssue


def _ids(issues: Iterable[SecurityIssue]) -> set[str]:
    return {i.rule_id for i in issues}


def _modern_handshake(**overrides: object) -> TlsHandshakeResult:
    base = dict(
        host="example.test",
        port=443,
        tls_version="TLSv1.3",
        cipher_name="TLS_AES_256_GCM_SHA384",
        cipher_bits=256,
        leaf_subject_cn="example.test",
        leaf_issuer_cn="Test CA",
        not_before=datetime.now(UTC) - timedelta(days=30),
        not_after=datetime.now(UTC) + timedelta(days=180),
        san=("example.test",),
        fingerprint_sha256="00" * 32,
        hsts_header="max-age=31536000; includeSubDomains",
    )
    base.update(overrides)
    return TlsHandshakeResult(**base)


def test_modern_handshake_yields_no_issues() -> None:
    handshake = _modern_handshake()
    assert list(evaluate_handshake(handshake)) == []


def test_legacy_protocol_flagged() -> None:
    handshake = _modern_handshake(tls_version="TLSv1")
    ids = _ids(evaluate_handshake(handshake))
    assert "SEC-TLS-VERSION-LEGACY" in ids


def test_weak_cipher_flagged() -> None:
    handshake = _modern_handshake(cipher_name="ECDHE-RSA-RC4-SHA")
    ids = _ids(evaluate_handshake(handshake))
    assert "SEC-TLS-WEAK-CIPHER" in ids


def test_cbc_under_tls12_flagged_medium() -> None:
    handshake = _modern_handshake(
        tls_version="TLSv1.2",
        cipher_name="ECDHE-RSA-AES128-CBC-SHA",
    )
    issues = list(evaluate_handshake(handshake))
    weak = next(i for i in issues if i.rule_id == "SEC-TLS-WEAK-CIPHER")
    assert weak.severity == "medium"


def test_expired_cert_flagged_critical() -> None:
    handshake = _modern_handshake(not_after=datetime.now(UTC) - timedelta(days=1))
    issues = list(evaluate_handshake(handshake))
    exp = next(i for i in issues if i.rule_id == "SEC-TLS-CERT-EXPIRED")
    assert exp.severity == "critical"


def test_expiring_soon_flagged_medium() -> None:
    handshake = _modern_handshake(not_after=datetime.now(UTC) + timedelta(days=7))
    issues = list(evaluate_handshake(handshake))
    soon = next(i for i in issues if i.rule_id == "SEC-TLS-CERT-EXPIRING-SOON")
    assert soon.severity == "medium"


def test_missing_hsts_flagged() -> None:
    handshake = _modern_handshake(hsts_header=None)
    ids = _ids(evaluate_handshake(handshake))
    assert "SEC-TLS-HSTS-MISSING" in ids


def test_short_hsts_flagged() -> None:
    handshake = _modern_handshake(hsts_header="max-age=600")
    ids = _ids(evaluate_handshake(handshake))
    assert "SEC-TLS-HSTS-TOO-SHORT" in ids


def test_parse_hsts_extracts_max_age() -> None:
    assert _parse_hsts_max_age("max-age=31536000; includeSubDomains") == 31_536_000
    assert _parse_hsts_max_age("includeSubDomains") is None
    assert _parse_hsts_max_age("max-age=abc") is None
