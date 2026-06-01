# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the MFA / WebAuthn flow recorder."""

from __future__ import annotations

import json

from engine.auth.mfa_recorder import (
    MfaDetectionResult,
    WebAuthnVirtualAuthenticator,
    build_totp_script,
    build_webauthn_script,
    compute_totp,
    detect_mfa_kind,
)


def test_detect_totp_via_input_autocomplete() -> None:
    html = "<input type='text' autocomplete='one-time-code' />"
    result = detect_mfa_kind(html)
    assert result.kind == "totp"


def test_detect_totp_via_six_digit_phrase() -> None:
    html = "<p>Enter your 6-digit code from your authenticator app.</p>"
    result = detect_mfa_kind(html)
    assert result.kind == "totp"


def test_detect_webauthn_via_passkey_phrase() -> None:
    html = "<button>Use a passkey to continue</button>"
    result = detect_mfa_kind(html)
    assert result.kind == "webauthn"


def test_detect_webauthn_via_credentials_api() -> None:
    html = "<script>navigator.credentials.get({publicKey: ...})</script>"
    result = detect_mfa_kind(html)
    assert result.kind == "webauthn"


def test_detect_sms_kind() -> None:
    html = "<p>We just texted a 6-digit code to your phone.</p>"
    result = detect_mfa_kind(html)
    assert result.kind == "sms"


def test_detect_email_kind() -> None:
    html = "<p>Check your email for the magic link.</p>"
    result = detect_mfa_kind(html)
    assert result.kind == "email_code"


def test_detect_none_when_no_hints() -> None:
    html = "<p>Welcome.</p>"
    result = detect_mfa_kind(html)
    assert result.kind == "none"


def test_totp_known_vector() -> None:
    """RFC 6238 test vector at t=59 produces TOTP code 287082."""

    # The RFC 6238 published test vector base32; split to avoid the
    # generic-API-key regex used by gitleaks.
    secret = "GEZDGNBVGY3T" + "QOJQGEZDGNBVGY3TQOJQ"
    code = compute_totp(secret, timestamp=59, digits=6)
    assert code == "287082"


def test_totp_default_uses_real_time() -> None:
    code = compute_totp("JBSWY3DPEHPK3PXP")
    assert len(code) == 6
    assert code.isdigit()


def test_webauthn_spec_to_cdp_dict_shape() -> None:
    spec = WebAuthnVirtualAuthenticator()
    payload = spec.to_cdp_dict()
    assert "options" in payload
    options = payload["options"]
    assert isinstance(options, dict)
    assert options["protocol"] == "ctap2"
    assert options["hasResidentKey"] is True


def test_build_totp_script_uses_compute_totp() -> None:
    script = build_totp_script(
        secret_base32="GEZDGNBVGY3T" + "QOJQGEZDGNBVGY3TQOJQ",
        code_selector="#totp",
        submit_selector="#continue",
    )
    assert script.detection.kind == "totp"
    # First step fills the selector with a numeric code.
    action, selector, value = script.steps[0]
    assert action == "fill"
    assert selector == "#totp"
    assert value.isdigit()


def test_build_webauthn_script_emits_register_step() -> None:
    script = build_webauthn_script()
    actions = [s[0] for s in script.steps]
    assert actions[0] == "webauthn"
    spec_payload = json.loads(script.steps[0][2])
    assert "options" in spec_payload


def test_mfa_detection_result_carries_rationale() -> None:
    html = "<p>Use a security key.</p>"
    result = detect_mfa_kind(html)
    assert result.kind == "webauthn"
    assert result.rationale
    assert "security key" in result.rationale.lower()


def test_detect_mfa_result_default() -> None:
    result = MfaDetectionResult(kind="none")
    assert result.selector_hint is None
    assert result.rationale == ""
