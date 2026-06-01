"""QualityScore entity."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import SCORE_SCHEMA_VERSION


class QualityScore(SentinelModel):
    """The reproducible quality score for one run."""

    SCHEMA_VERSION: ClassVar[str] = SCORE_SCHEMA_VERSION

    id: str
    run_id: str
    total: float = Field(ge=0.0, le=100.0)
    components: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    severity_penalties_applied: dict[str, float] = Field(default_factory=dict)
    schema_version: str = Field(default=SCORE_SCHEMA_VERSION)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="SCR")

    @field_validator("run_id")
    @classmethod
    def _check_run_id(cls, value: str) -> str:
        return validate_id(value, prefix="RUN")

    @field_validator("components", "weights", "severity_penalties_applied")
    @classmethod
    def _non_negative(cls, value: dict[str, float]) -> dict[str, float]:
        for k, v in value.items():
            if v < 0:
                raise ValueError(f"QualityScore[{k!r}] must be >= 0; got {v}.")
        return value


__all__ = ["QualityScore"]
