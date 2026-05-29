"""Fixture refresh proposals (Phase 20.04, CLAUDE.md §23).

When a data fixture (``seededRecord``) fails because the seeded
entity is missing or the API contract changed, the Healer never
auto-applies anything to the database. It emits a structured
*proposal* that tells the operator (or agent) which command to run.

Two patterns:

1. **Re-seed.** The fixture's last successful response named record
   ``id=42`` but the current API returns ``404``. We propose:
   "Re-run the project's seed command (default: ``pnpm seed``)".

2. **Regenerate from schema.** The fixture's expected shape diverges
   from the current OpenAPI/GraphQL schema (extra or missing fields).
   We propose: "Re-run ``sentinel generate --from-discovery`` to
   refresh fixture data files".

Confidence is fixed by the signal:

- Missing entity (404 / empty body) → ``0.85`` (auto-apply candidate
  under ``auto_apply_mode='aggressive'`` with operator approval; the
  default threshold of ``0.9`` still forces review).
- Contract drift (schema mismatch) → ``0.7`` (always review).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.diff import unified_diff_for
from engine.healer.models import RepairProposal

FixtureFailureKind = Literal["missing_entity", "contract_drift"]


@dataclass(frozen=True)
class FixtureRepairInputs:
    """Inputs for one fixture-repair proposal.

    The Healer never touches the fixture file directly. The
    ``unified_diff`` it produces only adds an explanatory comment near
    the failing fixture call so a reviewer can scan ``git diff`` for
    healer activity; the *actual* repair is the shell command in
    ``proposed_change``.
    """

    test_path: Path
    test_source: str
    fixture_call_line: int
    """1-based line where the failing fixture call appears."""

    failure_kind: FixtureFailureKind

    seed_command: str = "pnpm seed"
    """Command to run when ``failure_kind='missing_entity'``."""

    expected_fields: tuple[str, ...] = ()
    actual_fields: tuple[str, ...] = ()


def propose_fixture_repair(
    inputs: FixtureRepairInputs,
    *,
    id_generator: IdGenerator | None = None,
) -> RepairProposal:
    """Propose a fixture refresh. Always ``requires_human_review=True``."""

    lines = inputs.test_source.splitlines(keepends=True)
    if inputs.fixture_call_line < 1 or inputs.fixture_call_line > len(lines):
        # Defensive: tests can supply a synthetic source; we still want a
        # valid proposal so the calling pipeline isn't fragile.
        original_line = "// (fixture call line out of range)\n"
        target_idx = 0
    else:
        target_idx = inputs.fixture_call_line - 1
        original_line = lines[target_idx]

    if inputs.failure_kind == "missing_entity":
        confidence = 0.85
        reason = (
            "Fixture call returned 404 / empty body. The seeded record is "
            f"missing. Run `{inputs.seed_command}` to reseed."
        )
        action = inputs.seed_command
    else:
        confidence = 0.7
        missing = tuple(f for f in inputs.expected_fields if f not in inputs.actual_fields)
        extra = tuple(f for f in inputs.actual_fields if f not in inputs.expected_fields)
        reason = (
            "Fixture shape does not match the current API contract. "
            f"Missing fields: {missing or '()'}. Unexpected fields: {extra or '()'}. "
            "Regenerate the fixture from the current OpenAPI/GraphQL schema."
        )
        action = "sentinel generate --from-discovery"

    annotation = f"// HEALER PROPOSAL ({inputs.failure_kind}): {action}\n"
    proposed_lines = list(lines)
    if 0 <= target_idx < len(proposed_lines):
        proposed_lines.insert(target_idx, annotation)
    else:
        proposed_lines.append(annotation)
    proposed_source = "".join(proposed_lines)

    diff = unified_diff_for(
        path=str(inputs.test_path),
        original=inputs.test_source,
        proposed=proposed_source,
    )

    gen = id_generator or IdGenerator()
    return RepairProposal(
        id=gen.new("RPR"),
        kind="fixture",
        target_test=str(inputs.test_path),
        target_test_line=inputs.fixture_call_line,
        original_behavior=original_line.rstrip("\n"),
        proposed_change=f"Run `{action}` and re-execute the fixture.",
        confidence=confidence,
        reason=reason,
        evidence=(
            Evidence(
                id=gen.new("EVD"),
                type="source_ref",
                path=inputs.test_path,
            ),
        ),
        requires_human_review=True,
        unified_diff=diff,
        descriptor=None,
    )


__all__ = [
    "FixtureFailureKind",
    "FixtureRepairInputs",
    "propose_fixture_repair",
]
