"""Safety policy enforcement tests (PRD §2, CLAUDE.md §6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from engine.domain.target import Target
from engine.errors.base import DestructiveWithoutProofError, UnknownHostError
from engine.policy.audit_log import read_audit_log
from engine.policy.safety import SafetyPolicy, is_local


@pytest.fixture
def policy() -> SafetyPolicy:
    return SafetyPolicy()


def test_local_safe_allowed(policy: SafetyPolicy) -> None:
    t = Target(base_url="http://localhost:3000", allowed_hosts=["localhost"])
    decision = policy.enforce(t)
    assert decision.allowed is True
    assert decision.host == "localhost"


def test_127_local_allowed(policy: SafetyPolicy) -> None:
    t = Target(base_url="http://127.0.0.1:8080", allowed_hosts=())
    decision = policy.enforce(t)
    assert decision.allowed is True


def test_ipv6_local_allowed(policy: SafetyPolicy) -> None:
    t = Target(base_url="http://[::1]:3000", allowed_hosts=())
    decision = policy.enforce(t)
    assert decision.allowed is True


def test_rfc1918_local_allowed(policy: SafetyPolicy) -> None:
    t = Target(base_url="http://10.0.0.1:8080", allowed_hosts=())
    decision = policy.enforce(t)
    assert decision.allowed is True


def test_public_without_allowlist_blocked(policy: SafetyPolicy) -> None:
    t = Target(base_url="https://google.com", allowed_hosts=["staging.example.com"])
    with pytest.raises(UnknownHostError) as exc_info:
        policy.enforce(t)
    assert exc_info.value.exit_code == 4
    assert "google.com" in exc_info.value.message


def test_public_with_allowlist_allowed(policy: SafetyPolicy) -> None:
    t = Target(
        base_url="https://staging.example.com",
        allowed_hosts=["staging.example.com"],
    )
    decision = policy.enforce(t)
    assert decision.allowed is True


def test_audit_log_records_block(policy: SafetyPolicy, tmp_path: Path) -> None:
    t = Target(base_url="https://evil.example.com", allowed_hosts=["ok.example.com"])
    log = tmp_path / "audit.log"
    with pytest.raises(UnknownHostError):
        policy.enforce(t, audit_log_path=log)
    entries = read_audit_log(log)
    assert len(entries) == 1
    assert entries[0]["allowed"] is False
    assert entries[0]["host"] == "evil.example.com"


def test_audit_log_records_allow(policy: SafetyPolicy, tmp_path: Path) -> None:
    t = Target(base_url="http://localhost:3000", allowed_hosts=["localhost"])
    log = tmp_path / "audit.log"
    policy.enforce(t, audit_log_path=log)
    entries = read_audit_log(log)
    assert len(entries) == 1
    assert entries[0]["allowed"] is True


def test_destructive_without_proof_blocked(policy: SafetyPolicy) -> None:
    t = Target(
        base_url="http://localhost:3000",
        allowed_hosts=["localhost"],
        mode="authorized_destructive",
    )
    with pytest.raises(DestructiveWithoutProofError):
        policy.enforce(t)


def test_destructive_with_valid_proof(policy: SafetyPolicy, tmp_path: Path) -> None:
    proof = tmp_path / "proof.yaml"
    issued = datetime.now(UTC) - timedelta(days=1)
    expires = datetime.now(UTC) + timedelta(days=30)
    proof.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1",
                "host": "staging.example.com",
                "actor": "alice@example.com",
                "scope": ["destructive"],
                "issued_at": issued.isoformat(),
                "expires_at": expires.isoformat(),
            }
        )
    )
    t = Target(
        base_url="https://staging.example.com",
        allowed_hosts=["staging.example.com"],
        mode="authorized_destructive",
        proof_of_authorization=proof,
    )
    decision = policy.enforce(t)
    assert decision.allowed is True
    assert "alice@example.com" in " ".join(decision.evidence)


def test_destructive_with_expired_proof(policy: SafetyPolicy, tmp_path: Path) -> None:
    proof = tmp_path / "proof.yaml"
    issued = datetime.now(UTC) - timedelta(days=30)
    expires = datetime.now(UTC) - timedelta(days=1)
    proof.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1",
                "host": "staging.example.com",
                "actor": "alice@example.com",
                "scope": ["destructive"],
                "issued_at": issued.isoformat(),
                "expires_at": expires.isoformat(),
            }
        )
    )
    t = Target(
        base_url="https://staging.example.com",
        allowed_hosts=["staging.example.com"],
        mode="authorized_destructive",
        proof_of_authorization=proof,
    )
    with pytest.raises(DestructiveWithoutProofError):
        policy.enforce(t)


def test_is_local_helpers() -> None:
    assert is_local("localhost")
    assert is_local("127.0.0.1")
    assert is_local("::1")
    assert is_local("10.0.0.1")
    assert is_local("192.168.1.1")
    assert not is_local("8.8.8.8")
    assert not is_local("example.com")


def test_requires_proof_helper(policy: SafetyPolicy) -> None:
    t_safe = Target(base_url="http://localhost", allowed_hosts=["localhost"])
    assert policy.requires_proof_of_authorization(t_safe, "safe") is False
    assert policy.requires_proof_of_authorization(t_safe, "authorized_destructive") is True
