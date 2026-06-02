# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Mutation-guard tests for the safety boundary (v1.7.0, phase 37).

These tests exist specifically to *fail* under common mutations of
``SafetyPolicy.enforce``. They document the invariants that must hold
regardless of refactor:

* A public host without an allowlist entry MUST be refused.
* A destructive request without proof-of-authorization MUST be refused,
  including against loopback or allowlisted hosts.
* ``SafetyDecision`` cannot be constructed without an explicit ``allowed``
  value (no default that lets a refactor silently flip the boundary open).
* The audit log is written BEFORE the refusal exception escapes.

The mutation testing harness (``make mutation``) targets
``engine/policy/safety.py``. If any of these invariants is silently
removed, at least one assertion here must fail.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from engine.domain.target import Target
from engine.errors.base import (
    DestructiveWithoutProofError,
    UnknownHostError,
    UnsafeTargetError,
)
from engine.policy.safety import SafetyDecision, SafetyPolicy


@pytest.fixture
def policy() -> SafetyPolicy:
    return SafetyPolicy()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _write_proof(path: Path, *, expires_at: datetime, actor: str = "ohswedd@example.com") -> Path:
    issued = expires_at - timedelta(days=30)
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1",
                "host": "staging.example.com",
                "actor": actor,
                "scope": ["destructive"],
                "issued_at": issued.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# Allowlist mutation guards
# --------------------------------------------------------------------------- #


def test_public_host_without_allowlist_must_raise(
    policy: SafetyPolicy, fixed_now: datetime
) -> None:
    """If `enforce` ever returns `allowed=True` for an un-allowlisted public host,
    this test fails — that is the headline mutant.
    """

    target = Target(
        base_url="https://attacker.example.com",
        allowed_hosts=(),
    )

    with pytest.raises(UnknownHostError):
        policy.enforce(target, now=fixed_now)


def test_public_host_with_unrelated_allowlist_still_raises(
    policy: SafetyPolicy, fixed_now: datetime
) -> None:
    """An allowlist that does NOT cover the host must not save the request."""

    target = Target(
        base_url="https://attacker.example.com",
        allowed_hosts=("partner.example.com", "ops.example.com"),
    )

    with pytest.raises(UnknownHostError):
        policy.enforce(target, now=fixed_now)


# --------------------------------------------------------------------------- #
# Destructive-mode mutation guards
# --------------------------------------------------------------------------- #


def test_destructive_without_proof_must_raise_on_local(
    policy: SafetyPolicy, fixed_now: datetime
) -> None:
    """Destructive mode requires proof even on loopback. Mutating away that branch
    would allow ``127.0.0.1`` to be destructively scanned without paperwork.
    """

    target = Target(
        base_url="http://127.0.0.1:8080",
        mode="authorized_destructive",
        allowed_hosts=(),
    )

    with pytest.raises(UnsafeTargetError):
        policy.enforce(target, now=fixed_now)


def test_destructive_without_proof_must_raise_on_allowlisted_public(
    policy: SafetyPolicy, fixed_now: datetime
) -> None:
    """Allowlisted public hosts still need proof for destructive scans."""

    target = Target(
        base_url="https://staging.example.com",
        mode="authorized_destructive",
        allowed_hosts=("staging.example.com",),
    )

    with pytest.raises(DestructiveWithoutProofError):
        policy.enforce(target, now=fixed_now)


def test_destructive_with_expired_proof_must_raise(
    policy: SafetyPolicy, fixed_now: datetime, tmp_path: Path
) -> None:
    proof_path = _write_proof(tmp_path / "proof.yaml", expires_at=fixed_now - timedelta(days=1))
    target = Target(
        base_url="https://staging.example.com",
        mode="authorized_destructive",
        allowed_hosts=("staging.example.com",),
        proof_of_authorization=proof_path,
    )

    with pytest.raises(UnsafeTargetError):
        policy.enforce(target, now=fixed_now)


# --------------------------------------------------------------------------- #
# SafetyDecision constructor guards
# --------------------------------------------------------------------------- #


def test_safety_decision_allowed_has_no_default(fixed_now: datetime) -> None:
    """`allowed` has no default — a coder cannot accidentally construct an
    allowed decision by leaving the flag off."""

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SafetyDecision(  # type: ignore[call-arg]
            reason="loopback in safe mode",
            host="127.0.0.1",
            mode="safe",
            decided_at=fixed_now,
        )


def test_safety_decision_round_trip_preserves_allowed_flag(
    fixed_now: datetime,
) -> None:
    """If serialisation drops the `allowed` flag, downstream consumers would
    have to guess. The dict form must carry it verbatim."""

    decision = SafetyDecision(
        allowed=True,
        reason="loopback in safe mode",
        host="127.0.0.1",
        mode="safe",
        evidence=(),
        decided_at=fixed_now,
    )
    payload = decision.to_dict()
    assert payload["allowed"] is True

    refused = SafetyDecision(
        allowed=False,
        reason="public host not in allowlist",
        host="attacker.example.com",
        mode="safe",
        evidence=(),
        decided_at=fixed_now,
    )
    assert refused.to_dict()["allowed"] is False


# --------------------------------------------------------------------------- #
# Fail-closed audit-log guard
# --------------------------------------------------------------------------- #


def test_audit_log_is_written_before_refusal_propagates(
    policy: SafetyPolicy, fixed_now: datetime, tmp_path: Path
) -> None:
    """Mutating the order of ``write_audit_entry`` and ``raise`` would lose the
    audit trail. The log line must hit disk before the exception escapes the call.
    """

    log_path = tmp_path / "audit.log.jsonl"
    target = Target(
        base_url="https://attacker.example.com",
        allowed_hosts=(),
    )

    with pytest.raises(UnknownHostError):
        policy.enforce(target, now=fixed_now, audit_log_path=log_path)

    assert log_path.is_file(), "audit log must exist after a refusal"
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    record = json.loads(line)
    assert record["allowed"] is False
    assert record["host"] == "attacker.example.com"
