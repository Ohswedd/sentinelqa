"""RepairSuggestion entity (CLAUDE.md §23, PRD §9.6)."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.evidence import Evidence
from engine.domain.ids import validate_id
from engine.domain.schema import REPAIR_SUGGESTION_SCHEMA_VERSION


class RepairSuggestion(SentinelModel):
    """A healer-proposed locator or test repair (CLAUDE.md §23).

    Every field carries first-class evidence so reviewers can judge the
    proposal without re-running the failing test. Assertion-weakening or
    intent-changing repairs are forbidden by CLAUDE.md §23 and must be
    surfaced as ``requires_human_review=True``.
    """

    SCHEMA_VERSION: ClassVar[str] = REPAIR_SUGGESTION_SCHEMA_VERSION

    id: str
    target_test: str = Field(min_length=1, max_length=2048)
    original: str = Field(min_length=1, max_length=8000)
    proposed: str = Field(min_length=1, max_length=8000)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=4000)
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple)
    requires_human_review: bool = True
    schema_version: str = Field(default=REPAIR_SUGGESTION_SCHEMA_VERSION)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="RPR")

    def to_agent_message(self) -> dict[str, Any]:
        """Return the canonical agent-message dict for this suggestion.

        Shape matches the CLAUDE.md §23 healer-proposal contract.
        Delegates to the SDK builder so the domain entity and
        :class:`sentinelqa.Sentinel` consumers stay in lock-step.
        """

        from sentinelqa._agent_messages import (
            repair_suggestion_to_agent_message,
        )

        return repair_suggestion_to_agent_message(self)


__all__ = ["RepairSuggestion"]
