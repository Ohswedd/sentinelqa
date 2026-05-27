"""Flow entity (PRD §18.1).

A flow is an end-to-end user journey assembled from routes and elements.
The planner (Phase 06) produces flows; the generator (Phase 07) turns each
into one or more :class:`TestCase` files.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import CONFIG_SCHEMA_VERSION

Priority = Literal["P0", "P1", "P2", "P3"]
Risk = Literal["critical", "high", "medium", "low"]


class FlowStep(SentinelModel):
    """One step inside a :class:`Flow`."""

    description: str = Field(min_length=1, max_length=2000)
    target_route_id: str | None = None
    target_element_id: str | None = None
    expected_outcome: str = Field(min_length=1, max_length=2000)

    @field_validator("target_route_id")
    @classmethod
    def _check_route_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_id(value, prefix="RT")

    @field_validator("target_element_id")
    @classmethod
    def _check_element_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_id(value, prefix="EL")


class Flow(SentinelModel):
    """A named user journey through the app."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    name: str = Field(min_length=1, max_length=200)
    steps: tuple[FlowStep, ...]
    priority: Priority = "P2"
    risk: Risk = "medium"
    required_auth_role: str | None = Field(default=None, max_length=64)
    required_data_state: str | None = Field(default=None, max_length=200)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="FLW")

    @field_validator("steps")
    @classmethod
    def _require_at_least_one_step(cls, value: tuple[FlowStep, ...]) -> tuple[FlowStep, ...]:
        if len(value) == 0:
            raise ValueError("A Flow must contain at least one step.")
        return value


__all__ = ["Flow", "FlowStep", "Priority", "Risk"]
