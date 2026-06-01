"""PolicyDecision entity (the documentation)."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import RUN_SCHEMA_VERSION

ReleaseDecision = Literal[
    "pass",
    "pass_with_warnings",
    "blocked",
    "inconclusive",
    "unsafe_target_rejected",
]


class PolicyDecision(SentinelModel):
    """The release-gate decision derived from findings + policy."""

    SCHEMA_VERSION: ClassVar[str] = RUN_SCHEMA_VERSION

    id: str
    run_id: str
    release_decision: ReleaseDecision
    blocked_by: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    schema_version: str = Field(default=RUN_SCHEMA_VERSION)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="PD")

    @field_validator("run_id")
    @classmethod
    def _check_run_id(cls, value: str) -> str:
        return validate_id(value, prefix="RUN")


__all__ = ["PolicyDecision", "ReleaseDecision"]
