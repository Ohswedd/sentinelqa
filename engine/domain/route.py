"""Route entity (the documentation).

A route is one URL the app exposes — discovered by the crawler (Phase 05),
referenced by every later module for finding location.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import CONFIG_SCHEMA_VERSION

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def _default_methods() -> frozenset[HttpMethod]:
    """Default ``http_methods`` factory typed so mypy keeps the Literal narrowing."""

    methods: frozenset[HttpMethod] = frozenset({"GET"})
    return methods


class Route(SentinelModel):
    """A discovered URL exposed by the app."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    path: str = Field(min_length=1, max_length=2048)
    http_methods: frozenset[HttpMethod] = Field(default_factory=lambda: _default_methods())
    auth_required: bool = False
    parent_template: str | None = Field(default=None, max_length=2048)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="RT")


__all__ = ["Route", "HttpMethod"]
