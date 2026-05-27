"""RiskMap entity (PRD §18.1 — derived from DiscoveryGraph)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import CONFIG_SCHEMA_VERSION


class RouteRisk(SentinelModel):
    """Per-route risk score (0..1 normalized)."""

    route_id: str
    score: float = Field(ge=0.0, le=1.0)
    justifications: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("route_id")
    @classmethod
    def _check_route_id(cls, value: str) -> str:
        return validate_id(value, prefix="RT")


class RiskMap(SentinelModel):
    """Aggregated per-route risk derived from the discovery graph."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    entries: tuple[RouteRisk, ...] = Field(default_factory=tuple)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="RM")


__all__ = ["RiskMap", "RouteRisk"]
