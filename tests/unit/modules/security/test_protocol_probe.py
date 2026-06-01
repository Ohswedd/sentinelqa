# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the HTTP/2 + HTTP/3 negotiation probe."""

from __future__ import annotations

from modules.security.checks.protocol_probe import (
    ProtocolProbeResult,
    evaluate_protocol_probe,
    grade_protocol_support,
)


def test_evaluate_no_https_returns_single_critical_finding() -> None:
    probe = ProtocolProbeResult(host="app.example.com", is_https=False)
    findings = evaluate_protocol_probe(probe)
    assert len(findings) == 1
    assert findings[0].code == "PROTO-NO-HTTPS"
    assert findings[0].severity == "high"


def test_evaluate_full_support_returns_no_findings() -> None:
    probe = ProtocolProbeResult(
        host="app.example.com",
        is_https=True,
        alpn_offered=("h2", "http/1.1"),
        alpn_negotiated="h2",
        http2_supported=True,
        http3_supported=True,
        alt_svc_header='h3=":443"; ma=86400',
    )
    findings = evaluate_protocol_probe(probe)
    assert findings == ()


def test_evaluate_no_h2_returns_medium_finding() -> None:
    probe = ProtocolProbeResult(
        host="app.example.com",
        is_https=True,
        alpn_offered=("http/1.1",),
        alpn_negotiated="http/1.1",
        http2_supported=False,
        http3_supported=False,
    )
    findings = evaluate_protocol_probe(probe)
    codes = {f.code for f in findings}
    assert "PROTO-NO-H2" in codes
    assert "PROTO-NO-H3" in codes


def test_evaluate_alt_svc_without_h3_flags_info() -> None:
    probe = ProtocolProbeResult(
        host="app.example.com",
        is_https=True,
        http2_supported=True,
        http3_supported=False,
        alt_svc_header="clear",
    )
    findings = evaluate_protocol_probe(probe)
    codes = {f.code for f in findings}
    assert "PROTO-ALT-SVC-NO-H3" in codes


def test_grade_no_https_is_f() -> None:
    probe = ProtocolProbeResult(host="x", is_https=False)
    assert grade_protocol_support(probe) == "F"


def test_grade_h2_only_is_b() -> None:
    probe = ProtocolProbeResult(
        host="x", is_https=True, http2_supported=True, http3_supported=False
    )
    assert grade_protocol_support(probe) == "B"


def test_grade_h2_plus_h3_is_a() -> None:
    probe = ProtocolProbeResult(host="x", is_https=True, http2_supported=True, http3_supported=True)
    assert grade_protocol_support(probe) == "A"


def test_grade_h2_h3_and_alt_svc_is_a_plus() -> None:
    probe = ProtocolProbeResult(
        host="x",
        is_https=True,
        http2_supported=True,
        http3_supported=True,
        alt_svc_header='h3=":443"',
    )
    assert grade_protocol_support(probe) == "A+"


def test_grade_https_no_h2_h3_is_c() -> None:
    probe = ProtocolProbeResult(host="x", is_https=True)
    assert grade_protocol_support(probe) == "C"
