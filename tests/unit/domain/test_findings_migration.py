"""``findings`` v1 → v2 migration tests ( / ADR-0044)."""

from __future__ import annotations

from engine.domain.migrations import MIGRATIONS, run_migration
from engine.domain.migrations.findings_1_to_2 import migrate


def _v1_finding() -> dict:
    return {
        "id": "FND-LEGACYAAAAAA",
        "run_id": "RUN-LEGACYAAAAAA",
        "module": "security",
        "category": "security/headers/sec-headers-csp-missing",
        "severity": "medium",
        "confidence": 0.9,
        "title": "CSP missing",
        "description": "no Content-Security-Policy header",
        "location": {"route": "/", "selector": None, "file": None, "line": None},
        "evidence": [],
        "reproduction_steps": [],
        "suggested_fix": None,
        "recommendation": None,
        "affected_target": None,
        "created_at": "2026-01-01T00:00:00Z",
        "schema_version": "1",
    }


def test_migrate_registered_in_global_map() -> None:
    assert MIGRATIONS[("findings", "1", "2")] is migrate


def test_migrate_single_finding_stamps_v2_and_nulls_taxonomy() -> None:
    upgraded = migrate(_v1_finding())
    assert upgraded["schema_version"] == "2"
    assert upgraded["cwe_id"] is None
    assert upgraded["attack_id"] is None
    assert upgraded["owasp_api_id"] is None


def test_migrate_envelope_upgrades_each_finding() -> None:
    envelope = {
        "schema_version": "1",
        "run_id": "RUN-LEGACYAAAAAA",
        "generated_at": "2026-01-01T00:00:00Z",
        "count": 2,
        "findings": [_v1_finding(), _v1_finding()],
    }
    upgraded = migrate(envelope)
    assert upgraded["schema_version"] == "2"
    assert len(upgraded["findings"]) == 2
    for f in upgraded["findings"]:
        assert f["schema_version"] == "2"
        assert f["cwe_id"] is None


def test_migrate_idempotent_on_v2_input() -> None:
    v2_finding = migrate(_v1_finding())
    second_pass = migrate(v2_finding)
    assert second_pass == v2_finding


def test_run_migration_dispatches_to_registered_migrator() -> None:
    out = run_migration("findings", "1", "2", _v1_finding())
    assert out["schema_version"] == "2"


def test_migrate_preserves_existing_cwe_when_already_present() -> None:
    v1 = _v1_finding()
    # An odd in-flight doc that already carries cwe_id (e.g. produced
    # by an unrelated tool) should not have it clobbered.
    v1["cwe_id"] = "CWE-693"
    upgraded = migrate(v1)
    assert upgraded["cwe_id"] == "CWE-693"
