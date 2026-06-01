# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for PII detection in response bodies."""

from __future__ import annotations

from modules.security.checks.pii_in_responses import scan_body_for_pii


def test_ssn_match_is_critical_and_masked() -> None:
    body = '{"taxpayer_id": "123-45-6789"}'
    matches = scan_body_for_pii(body)
    assert any(m.category == "ssn" for m in matches)
    ssn = next(m for m in matches if m.category == "ssn")
    assert ssn.severity == "critical"
    assert "6789" in ssn.preview
    assert "123" not in ssn.preview  # area redacted


def test_ssn_with_invalid_area_is_skipped() -> None:
    body = '"666-12-3456" "000-12-3456" "912-12-3456"'
    matches = scan_body_for_pii(body)
    assert all(m.category != "ssn" for m in matches)


def test_credit_card_via_luhn() -> None:
    valid_pan = "4242 4242 4242 4242"  # Stripe test card, passes Luhn
    invalid = "1234 5678 9012 3456"  # fails Luhn
    body = f"{valid_pan} ... {invalid}"
    matches = scan_body_for_pii(body)
    pans = [m for m in matches if m.category == "credit_card"]
    assert len(pans) == 1
    assert pans[0].severity == "critical"
    assert "4242" in pans[0].preview
    assert "4242 4242 4242 4242" not in pans[0].preview


def test_email_detection_and_masking() -> None:
    body = "Contact alice.smith@example.com or bob@example.org"
    matches = [m for m in scan_body_for_pii(body) if m.category == "email"]
    assert len(matches) == 2
    assert any(p.preview.startswith("a***") and "@example.com" in p.preview for p in matches)
    assert any(p.preview.startswith("b***") and "@example.org" in p.preview for p in matches)


def test_phone_detection() -> None:
    body = "Reach us at (415) 555-1212 or +1-415-555-1234."
    matches = [m for m in scan_body_for_pii(body) if m.category == "phone_us"]
    assert len(matches) == 2
    assert all("1212" in m.preview or "1234" in m.preview for m in matches)


def test_ipv4_detection_ignores_loopback() -> None:
    body = "203.0.113.7 made a request from 127.0.0.1 and 10.0.0.5"
    matches = [m for m in scan_body_for_pii(body) if m.category == "ipv4"]
    assert len(matches) == 1
    assert "203.0" in matches[0].preview


def test_iban_detection() -> None:
    body = "Wire to DE89370400440532013000 for the EU contract."
    matches = [m for m in scan_body_for_pii(body) if m.category == "iban"]
    assert len(matches) == 1
    assert matches[0].severity == "high"
    assert matches[0].preview.startswith("DE89")


def test_zip_plus_4_detection() -> None:
    body = "ZIP code 94103-1234."
    matches = [m for m in scan_body_for_pii(body) if m.category == "zip_plus4"]
    assert len(matches) == 1
    assert matches[0].preview == "94103-****"


def test_binary_content_type_skipped() -> None:
    body = "alice@example.com"
    assert scan_body_for_pii(body, content_type="image/png") == ()
    assert scan_body_for_pii(body, content_type="application/octet-stream") == ()


def test_text_content_type_scanned() -> None:
    body = "alice@example.com"
    matches = scan_body_for_pii(body, content_type="application/json; charset=utf-8")
    assert any(m.category == "email" for m in matches)


def test_max_findings_caps_results() -> None:
    body = " ".join(f"user{i}@example.com" for i in range(500))
    matches = scan_body_for_pii(body, max_findings=10)
    assert len(matches) == 10


def test_offset_is_recorded() -> None:
    body = " " * 50 + "alice@example.com"
    matches = scan_body_for_pii(body)
    email = next(m for m in matches if m.category == "email")
    assert email.offset == 50


def test_pan_masking_keeps_only_first_six_last_four() -> None:
    body = "4242 4242 4242 4242"
    matches = scan_body_for_pii(body)
    pan = next(m for m in matches if m.category == "credit_card")
    assert pan.preview == "424242...4242"


def test_results_sorted_by_offset() -> None:
    body = "user@example.com 192.0.2.10 123-45-6789"
    matches = scan_body_for_pii(body)
    offsets = [m.offset for m in matches]
    assert offsets == sorted(offsets)
