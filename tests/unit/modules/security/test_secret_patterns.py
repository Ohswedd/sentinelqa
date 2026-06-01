"""Unit tests for the detection-mode secret patterns."""

from __future__ import annotations

from modules.security.secret_patterns import scan_for_pii, scan_for_secrets


def test_detects_aws_access_key() -> None:
    matches = scan_for_secrets("config = { ak: 'AKIAIOSFODNN7EXAMPLE' }")
    assert any(m.category == "aws_access_key_id" for m in matches)
    aws = next(m for m in matches if m.category == "aws_access_key_id")
    # Preview must NOT contain the rest of the secret.
    assert "AKIA" in aws.preview
    assert "EXAMPLE" not in aws.preview


def test_detects_jwt() -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ4In0.signaturepartsignature"
    matches = scan_for_secrets(jwt)
    assert any(m.category == "jwt" for m in matches)


def test_detects_github_token() -> None:
    matches = scan_for_secrets("export GH=ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert any(m.category == "github_token" for m in matches)


def test_detects_generic_api_key_assignment() -> None:
    matches = scan_for_secrets("const api_key = 'A1B2C3D4E5F6G7H8I9J0K1L2M3N4'")
    assert any(m.category == "generic_api_key" for m in matches)


def test_low_entropy_value_not_flagged() -> None:
    matches = scan_for_secrets("api_key = 'changeme'")
    assert matches == ()


def test_private_key_block_detected() -> None:
    text = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
    matches = scan_for_secrets(text)
    assert any(m.category == "private_key_block" for m in matches)


def test_scan_for_pii_masks_email() -> None:
    matches = scan_for_pii("Contact: alice.bob@example.com")
    assert matches
    assert "alice.bob@example.com" not in matches[0].preview
    assert "@example.com" in matches[0].preview


def test_scan_for_pii_masks_phone() -> None:
    matches = scan_for_pii("Call us at +1 (555) 123-4567")
    assert matches
    assert "1234567" not in matches[0].preview
    assert matches[0].preview.endswith("4567")


def test_empty_text_returns_empty_tuple() -> None:
    assert scan_for_secrets("") == ()
    assert scan_for_pii("") == ()
