"""Finding schema v2 — round-trip + forward-compat with v1 (task 32.09)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from engine.domain import Finding, IdGenerator
from engine.domain.schema import FINDINGS_SCHEMA_VERSION

GEN = IdGenerator()


def _base_kwargs() -> dict:
    return {
        "id": GEN.new("FND"),
        "run_id": GEN.new("RUN"),
        "module": "security",
        "category": "security/jwt/alg_none",
        "severity": "critical",
        "confidence": 0.99,
        "title": "JWT alg=none accepted",
        "description": "Server accepted a JWT with alg=none.",
        "created_at": datetime.now(UTC),
    }


def test_v2_constant_is_two() -> None:
    assert FINDINGS_SCHEMA_VERSION == "2"


def test_v2_finding_carries_taxonomy_ids() -> None:
    f = Finding(
        **_base_kwargs(),
        cwe_id="CWE-347",
        attack_id="T1606.001",
        owasp_api_id="API-2023-08",
    )
    payload = f.to_dict()
    assert payload["schema_version"] == "2"
    assert payload["cwe_id"] == "CWE-347"
    assert payload["attack_id"] == "T1606.001"
    assert payload["owasp_api_id"] == "API-2023-08"


def test_v2_finding_defaults_taxonomy_ids_to_none() -> None:
    f = Finding(**_base_kwargs())
    payload = f.to_dict()
    assert payload["cwe_id"] is None
    assert payload["attack_id"] is None
    assert payload["owasp_api_id"] is None


def test_v1_finding_parses_as_v2_with_null_taxonomy() -> None:
    """A pre-v2 wire dict (no taxonomy keys, schema_version="1") must parse."""

    legacy: dict = dict(_base_kwargs())
    legacy["schema_version"] = "1"
    legacy["id"] = "FND-LEGACYAAAAAA"
    legacy["run_id"] = "RUN-LEGACYAAAAAA"
    legacy["created_at"] = legacy["created_at"].isoformat()
    f = Finding.model_validate(legacy)
    assert f.cwe_id is None
    assert f.attack_id is None
    assert f.owasp_api_id is None
    # Field-level schema_version is preserved when the source claims v1;
    # the migration helper is the canonical path to stamp v2 explicitly.
    assert f.schema_version == "1"


def test_v2_finding_rejects_malformed_cwe_id() -> None:
    with pytest.raises(ValueError):
        Finding(**_base_kwargs(), cwe_id="cwe-347")  # lower-case prefix not allowed


def test_v2_finding_rejects_malformed_attack_id() -> None:
    with pytest.raises(ValueError):
        Finding(**_base_kwargs(), attack_id="1606.001")  # missing leading 'T'


def test_v2_finding_rejects_malformed_owasp_api_id() -> None:
    with pytest.raises(ValueError):
        Finding(**_base_kwargs(), owasp_api_id="API_2023_01")  # wrong separator


def test_v2_round_trip_via_dict() -> None:
    original = Finding(
        **_base_kwargs(),
        cwe_id="CWE-918",
        attack_id="T1190",
        owasp_api_id="API-2023-07",
    )
    payload = original.to_dict()
    reloaded = Finding.model_validate(payload)
    assert reloaded == original
