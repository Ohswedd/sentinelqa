"""ApiEndpoint entity (PRD §18.1)."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.route import HttpMethod
from engine.domain.schema import CONFIG_SCHEMA_VERSION

ApiEndpointSource = Literal["discovered", "openapi", "graphql", "user_provided"]


class ApiEndpoint(SentinelModel):
    """An HTTP / GraphQL endpoint the app exposes."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    method: HttpMethod
    path: str = Field(min_length=1, max_length=2048)
    request_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    auth_strategy: Literal["none", "bearer", "cookie", "basic", "api_key", "oauth", "unknown"] = (
        "unknown"
    )
    source: ApiEndpointSource = "discovered"

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="API")


__all__ = ["ApiEndpoint", "ApiEndpointSource"]
