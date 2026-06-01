"""Generated proposals validate against the JSON Schema.

The Healer's wire envelope is locked at
``packages/shared-schema/repair-proposal.schema.json`` (Draft 2020-12,
ADR-0025). This test exercises every kind to ensure the writer emits
schema-valid documents for the canonical paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.locator_repair import (
    DomCandidate,
    LocatorRepairInputs,
    propose_locator_repair,
)
from engine.healer.models import LocatorDescriptor, RepairProposal
from engine.healer.wait_repair import WaitRepairInputs, propose_wait_repair
from engine.healer.writer import write_proposal

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "shared-schema"
    / "repair-proposal.schema.json"
)


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return dict(document)


def test_locator_proposal_validates(tmp_path: Path, schema: dict[str, object]) -> None:
    candidates = [
        DomCandidate(
            role="button",
            accessible_name="Sign in",
            text="Sign in",
            landmarks=("form",),
            tag_name="button",
        )
    ]
    src = "const btn = page.getByRole('button', { name: /sign in/i });\n" "await btn.click();\n"
    proposal = propose_locator_repair(
        LocatorRepairInputs(
            test_path=Path("login.spec.ts"),
            test_source=src,
            locator_line=1,
            descriptor=LocatorDescriptor(
                role="button", accessible_name="Sign in", landmarks=("form",)
            ),
            dom_candidates=candidates,
        )
    )
    assert proposal is not None
    out = write_proposal(tmp_path, proposal)
    document = json.loads(out.read_text(encoding="utf-8"))
    jsonschema.validate(instance=document, schema=schema)


def test_wait_proposal_validates(tmp_path: Path, schema: dict[str, object]) -> None:
    src = (
        "await page.waitForTimeout(500);\n"
        "await expect(page.getByRole('heading')).toBeVisible();\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("a.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is not None
    out = write_proposal(tmp_path, proposal)
    document = json.loads(out.read_text(encoding="utf-8"))
    jsonschema.validate(instance=document, schema=schema)


def test_fixture_proposal_validates(tmp_path: Path, schema: dict[str, object]) -> None:
    from engine.healer.fixture_repair import (
        FixtureRepairInputs,
        propose_fixture_repair,
    )

    proposal = propose_fixture_repair(
        FixtureRepairInputs(
            test_path=Path("a.spec.ts"),
            test_source="const r = await seededRecord('user');\n",
            fixture_call_line=1,
            failure_kind="missing_entity",
        )
    )
    out = write_proposal(tmp_path, proposal)
    document = json.loads(out.read_text(encoding="utf-8"))
    jsonschema.validate(instance=document, schema=schema)


def test_assertion_kind_validates(tmp_path: Path, schema: dict[str, object]) -> None:
    """The schema allows assertion kind — covered for future Phase-20+ work."""

    gen = IdGenerator()
    proposal = RepairProposal(
        id=gen.new("RPR"),
        kind="assertion",
        target_test="a.spec.ts",
        original_behavior="expect(x).toBe(true)",
        proposed_change="expect(x).toBeTruthy()",
        confidence=0.5,
        reason="Stabilize loose equality.",
        evidence=(Evidence(id=gen.new("EVD"), type="source_ref", path=Path("a.spec.ts")),),
        requires_human_review=True,
        unified_diff="--- a\n+++ b\n@@\n-old\n+new\n",
    )
    out = write_proposal(tmp_path, proposal)
    document = json.loads(out.read_text(encoding="utf-8"))
    jsonschema.validate(instance=document, schema=schema)


def test_schema_id_is_pinned(schema: dict[str, object]) -> None:
    assert schema.get("title") == "RepairProposal"
    assert schema.get("x-sentinelqa-schema-version") == "1"
