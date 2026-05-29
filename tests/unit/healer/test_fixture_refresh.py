"""Phase 20.04 — Fixture refresh proposals."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.healer.fixture_repair import (
    FixtureRepairInputs,
    propose_fixture_repair,
)


def test_missing_entity_proposes_reseed() -> None:
    src = "const row = await seededRecord('user', { id: 42 });\n"
    proposal = propose_fixture_repair(
        FixtureRepairInputs(
            test_path=Path("t.spec.ts"),
            test_source=src,
            fixture_call_line=1,
            failure_kind="missing_entity",
            seed_command="pnpm db:seed",
        )
    )
    assert proposal.kind == "fixture"
    assert "pnpm db:seed" in proposal.proposed_change
    assert "404" in proposal.reason or "missing" in proposal.reason
    assert proposal.confidence == pytest.approx(0.85)
    assert proposal.requires_human_review is True
    assert "HEALER PROPOSAL (missing_entity)" in proposal.unified_diff


def test_contract_drift_proposes_regenerate() -> None:
    src = "const row = await seededRecord('user');\n"
    proposal = propose_fixture_repair(
        FixtureRepairInputs(
            test_path=Path("t.spec.ts"),
            test_source=src,
            fixture_call_line=1,
            failure_kind="contract_drift",
            expected_fields=("id", "email", "name"),
            actual_fields=("id", "email", "fullName"),
        )
    )
    assert proposal.kind == "fixture"
    assert "sentinel generate --from-discovery" in proposal.proposed_change
    assert "name" in proposal.reason  # missing field
    assert "fullName" in proposal.reason  # extra field
    assert proposal.confidence == pytest.approx(0.7)
    assert proposal.requires_human_review is True


def test_out_of_range_line_still_yields_proposal() -> None:
    proposal = propose_fixture_repair(
        FixtureRepairInputs(
            test_path=Path("t.spec.ts"),
            test_source="",
            fixture_call_line=99,
            failure_kind="missing_entity",
        )
    )
    assert proposal.kind == "fixture"
    assert proposal.confidence == pytest.approx(0.85)


def test_proposal_emits_unified_diff_header() -> None:
    proposal = propose_fixture_repair(
        FixtureRepairInputs(
            test_path=Path("t.spec.ts"),
            test_source="seededRecord('user');\n",
            fixture_call_line=1,
            failure_kind="missing_entity",
        )
    )
    assert proposal.unified_diff.startswith("--- t.spec.ts")
