"""Tests for the forbidden-capability registry (PRD §2.1, CLAUDE.md §6)."""

from __future__ import annotations

import pytest
from engine.errors.base import ForbiddenFlagError
from engine.policy.forbidden_features import (
    FORBIDDEN_CAPABILITIES,
    FORBIDDEN_CLI_FLAGS,
    assert_capability_allowed,
    assert_flag_allowed,
)


def test_required_capabilities_present() -> None:
    required = {
        "bot_detection_bypass",
        "captcha_bypass",
        "stealth_automation",
        "fingerprint_evasion",
        "credential_stuffing",
        "proxy_rotation_for_evasion",
        "rate_limit_bypass",
    }
    assert required <= FORBIDDEN_CAPABILITIES


def test_required_flags_present() -> None:
    required = {"--stealth", "--evade", "--bypass", "--undetectable"}
    assert required <= FORBIDDEN_CLI_FLAGS


def test_capability_rejected() -> None:
    with pytest.raises(ForbiddenFlagError):
        assert_capability_allowed("captcha_bypass")


def test_flag_rejected() -> None:
    with pytest.raises(ForbiddenFlagError):
        assert_flag_allowed("--stealth")


def test_unknown_capability_allowed() -> None:
    # Things not on the list pass silently — the deny list is closed.
    assert_capability_allowed("custom_legit_feature")
    assert_flag_allowed("--verbose")
