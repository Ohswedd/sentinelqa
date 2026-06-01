"""Wire-model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.security.models import (
    SECURITY_RESULT_SCHEMA_VERSION,
    SecurityCheckResult,
    SecurityIssue,
    SecurityRunOutcome,
)


def test_security_issue_rule_id_prefix_enforced() -> None:
    with pytest.raises(ValidationError):
        SecurityIssue(
            rule_id="BAD-NO-SEC",
            severity="low",
            confidence=0.5,
            title="x",
            description="y",
        )


def test_security_run_outcome_roundtrip() -> None:
    outcome = SecurityRunOutcome(
        schema_version=SECURITY_RESULT_SCHEMA_VERSION,
        checks=(
            SecurityCheckResult(
                check="headers",
                targets_scanned=1,
                issues=(
                    SecurityIssue(
                        rule_id="SEC-HEADERS-HSTS-MISSING",
                        severity="high",
                        confidence=0.9,
                        title="HSTS missing",
                        description="missing on https",
                    ),
                ),
                duration_ms=10,
            ),
        ),
        duration_ms=10,
    )
    serialized = outcome.model_dump(mode="json")
    reconstructed = SecurityRunOutcome.model_validate(serialized)
    assert reconstructed == outcome
