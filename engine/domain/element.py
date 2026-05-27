"""Element entity (PRD §18.1).

A semantic DOM element captured by discovery (Phase 05) and referenced by
generated tests (Phase 07) so selectors can be regenerated from the
accessibility tree rather than brittle CSS paths.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import CONFIG_SCHEMA_VERSION


class Element(SentinelModel):
    """An interactive element (button, link, input, etc.)."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    role: str = Field(min_length=1, max_length=64)
    accessible_name: str | None = Field(default=None, max_length=512)
    selector: str = Field(min_length=1, max_length=2048)
    route_id: str
    tags: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="EL")

    @field_validator("route_id")
    @classmethod
    def _check_route_id(cls, value: str) -> str:
        return validate_id(value, prefix="RT")


__all__ = ["Element"]
