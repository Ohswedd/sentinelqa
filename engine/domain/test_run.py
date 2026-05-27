"""TestRun entity (PRD §18.1).

The top-level container for one audit invocation. References every module
result, holds the snapshotted config, and decides whether the run is
``passed`` / ``failed`` / ``incomplete`` / ``unsafe_blocked``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import RUN_SCHEMA_VERSION
from engine.domain.target import Target

RunStatus = Literal["passed", "failed", "incomplete", "unsafe_blocked"]


class TestRun(SentinelModel):
    """One end-to-end SentinelQA audit invocation."""

    SCHEMA_VERSION: ClassVar[str] = RUN_SCHEMA_VERSION

    id: str
    started_at: datetime
    finished_at: datetime | None = None
    target: Target
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    modules_run: tuple[str, ...] = Field(default_factory=tuple)
    status: RunStatus = "incomplete"
    schema_version: str = Field(default=RUN_SCHEMA_VERSION)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="RUN")

    @field_validator("started_at", "finished_at")
    @classmethod
    def _require_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Datetimes on TestRun must be timezone-aware " "(use datetime.now(timezone.utc))."
            )
        return value.astimezone(UTC)


__all__ = ["TestRun", "RunStatus"]
