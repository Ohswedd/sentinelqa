"""Healer wire types (the documentation, our engineering rules).

The Healer emits :class:`RepairProposal` records. The shape is locked
under ADR-0025 and mirrored by
``packages/shared-schema/repair-suggestion.schema.json``.

A proposal is a strict superset of the Phase-01
:class:`engine.domain.repair_suggestion.RepairSuggestion` envelope. We
keep the domain model authoritative for the agent-message surface
( SDK) and use :class:`RepairProposal` for persistence and
CLI tooling so the extra fields (``unified_diff``, ``kind``,
``target_test_line``, ``descriptor``) don't leak into Phase-01.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.evidence import Evidence
from engine.domain.ids import validate_id
from engine.domain.schema import REPAIR_SUGGESTION_SCHEMA_VERSION

RepairKind = Literal["locator", "wait", "fixture", "assertion"]
"""Closed set per our engineering rules / the documentation.

``assertion`` is reserved for assertion-stabilization repairs (Phase
20.06 task). Auto-apply of ``assertion`` repairs is forbidden unless
the operator passes ``--allow-weaken``."""


class LocatorDescriptor(SentinelModel):
    """Snapshot of a Playwright locator's accessibility surface.

    Mirrors the Phase-04 TypeScript ``LocatorDescriptor`` (see
    ``packages/ts-runtime/src/locators.ts``) so the Python Healer can
    reason over descriptors captured by the runner without re-evaluating
    the page.
    """

    role: str | None = Field(default=None, max_length=128)
    accessible_name: str | None = Field(default=None, max_length=512)
    text: str | None = Field(default=None, max_length=512)
    landmarks: tuple[str, ...] = Field(default_factory=tuple)
    tag_name: str | None = Field(default=None, max_length=64)


class RepairProposal(SentinelModel):
    """One healer-proposed repair (ADR-0025).

    Schema version pinned to :data:`REPAIR_SUGGESTION_SCHEMA_VERSION` —
    the Phase-01 domain :class:`RepairSuggestion` uses the same
    constant so a single drift event affects both writers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = REPAIR_SUGGESTION_SCHEMA_VERSION

    id: str
    kind: RepairKind
    target_test: str = Field(min_length=1, max_length=2048)
    target_test_line: int | None = Field(default=None, ge=1, le=1_000_000)
    original_behavior: str = Field(min_length=1, max_length=8000)
    proposed_change: str = Field(min_length=1, max_length=8000)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=4000)
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple)
    requires_human_review: bool = True
    unified_diff: str = Field(min_length=1, max_length=64_000)
    descriptor: LocatorDescriptor | None = None
    schema_version: str = Field(default=REPAIR_SUGGESTION_SCHEMA_VERSION)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="RPR")

    @field_validator("unified_diff")
    @classmethod
    def _check_diff_shape(cls, value: str) -> str:
        # We don't apply the diff here; we only check that it looks like a
        # unified-diff (begins with ``--- `` / ``+++ ``). This catches the
        # accidental-empty-string and "raw replacement" mistakes early.
        first_line, _, _ = value.partition("\n")
        if not first_line.startswith("--- "):
            raise ValueError("unified_diff must begin with '--- ' (standard unified-diff header)")
        return value

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready dict written to ``<run-dir>/healer/<id>.json``."""

        return self.model_dump(mode="json")


__all__ = [
    "LocatorDescriptor",
    "RepairKind",
    "RepairProposal",
]
