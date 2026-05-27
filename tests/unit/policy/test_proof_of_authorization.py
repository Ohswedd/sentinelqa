"""Proof-of-authorization loader + verifier tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from engine.errors.base import ConfigFileNotFoundError, ConfigSchemaError
from engine.policy.proof_of_authorization import ProofOfAuthorization, load_proof, require_proof


def _proof_dict(host: str = "staging.example.com", scope: list[str] | None = None) -> dict:
    return {
        "schema_version": "1",
        "host": host,
        "actor": "alice@example.com",
        "scope": scope or ["destructive", "functional"],
        "issued_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }


def test_load_proof_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigFileNotFoundError):
        load_proof(tmp_path / "nope.yaml")


def test_load_proof_invalid_yaml(tmp_path: Path) -> None:
    proof = tmp_path / "proof.yaml"
    proof.write_text(":\n  - broken: :")
    with pytest.raises(ConfigSchemaError):
        load_proof(proof)


def test_load_proof_root_not_mapping(tmp_path: Path) -> None:
    proof = tmp_path / "proof.yaml"
    proof.write_text("[one, two]\n")
    with pytest.raises(ConfigSchemaError):
        load_proof(proof)


def test_load_proof_naive_datetime_rejected(tmp_path: Path) -> None:
    proof = tmp_path / "proof.yaml"
    data = _proof_dict()
    data["issued_at"] = "2026-01-01T00:00:00"
    proof.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigSchemaError):
        load_proof(proof)


def test_covers_host_case_insensitive() -> None:
    proof = ProofOfAuthorization.model_validate(_proof_dict("Staging.Example.COM"))
    assert proof.covers(host="STAGING.example.com", capability="destructive") is True


def test_does_not_cover_other_capability() -> None:
    proof = ProofOfAuthorization.model_validate(_proof_dict(scope=["functional"]))
    assert proof.covers(host="staging.example.com", capability="destructive") is False


def test_require_proof_with_none_path_raises() -> None:
    from engine.errors.base import DestructiveWithoutProofError

    with pytest.raises(DestructiveWithoutProofError):
        require_proof(None, host="staging.example.com")
