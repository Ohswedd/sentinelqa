"""DiscoveryGraph entity."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.base import SentinelModel
from engine.domain.element import Element
from engine.domain.form import Form
from engine.domain.ids import validate_id
from engine.domain.route import Route
from engine.domain.schema import CONFIG_SCHEMA_VERSION


class AuthBoundary(SentinelModel):
    """A boundary between authenticated and anonymous routes."""

    route_id: str
    required_role: str | None = Field(default=None, max_length=64)
    enforced_server_side: bool = True

    @field_validator("route_id")
    @classmethod
    def _check_route_id(cls, value: str) -> str:
        return validate_id(value, prefix="RT")


class DiscoveryGraph(SentinelModel):
    """The graph produced by the discovery module."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    routes: tuple[Route, ...] = Field(default_factory=tuple)
    elements: tuple[Element, ...] = Field(default_factory=tuple)
    forms: tuple[Form, ...] = Field(default_factory=tuple)
    api_endpoints: tuple[ApiEndpoint, ...] = Field(default_factory=tuple)
    auth_boundaries: tuple[AuthBoundary, ...] = Field(default_factory=tuple)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="DG")


__all__ = ["DiscoveryGraph", "AuthBoundary"]
