# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the Attestation provenance entity."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from engine.domain import Attestation, Finding, FindingLocation
from pydantic import ValidationError


def _attestation(**overrides: object) -> Attestation:
    defaults: dict[str, object] = {
        "check_name": "security.headers.csp_missing",
        "rule_id": "CWE-1021",
        "rule_version": "owasp-asvs-4.0.3",
        "sentinelqa_commit": "0123abc",
        "decided_at": datetime(2026, 6, 2, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Attestation.model_validate(defaults)


def test_round_trip_preserves_all_fields() -> None:
    attestation = _attestation()
    again = Attestation.model_validate_json(attestation.model_dump_json())
    assert again == attestation


def test_decided_at_must_be_tz_aware() -> None:
    with pytest.raises(ValidationError):
        _attestation(decided_at=datetime(2026, 6, 2))


def test_commit_hex_only() -> None:
    with pytest.raises(ValidationError):
        _attestation(sentinelqa_commit="not-a-hex")


def test_commit_min_length_enforced() -> None:
    with pytest.raises(ValidationError):
        _attestation(sentinelqa_commit="abc")


def test_rule_version_rejects_whitespace() -> None:
    with pytest.raises(ValidationError):
        _attestation(rule_version="bad version")


def test_finding_attestation_defaults_to_none() -> None:
    finding = Finding(
        id="FND-XAAAAAAAAAAA",
        run_id="RUN-XAAAAAAAAAAA",
        module="security",
        category="headers",
        severity="high",
        confidence=0.9,
        title="missing CSP",
        description="The application is missing Content-Security-Policy.",
        location=FindingLocation(),
        created_at=datetime(2026, 6, 2, tzinfo=UTC),
    )
    assert finding.attestation is None


def test_finding_carries_attestation_when_supplied() -> None:
    attestation = _attestation()
    finding = Finding(
        id="FND-XAAAAAAAAAAA",
        run_id="RUN-XAAAAAAAAAAA",
        module="security",
        category="headers",
        severity="high",
        confidence=0.9,
        title="missing CSP",
        description="The application is missing Content-Security-Policy.",
        location=FindingLocation(),
        attestation=attestation,
        created_at=datetime(2026, 6, 2, tzinfo=UTC),
    )
    assert finding.attestation == attestation
    raw = finding.model_dump_json()
    assert "attestation" in raw
    assert "0123abc" in raw
