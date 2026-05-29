"""Wire types emitted by :class:`ApiModule` (Phase 22, PRD §10.3).

The module persists ``api/<check>.json`` per check plus an
``api/index.json`` aggregate (mirrors the security module's layout).
:class:`ApiSchemaSnapshot` is the artifact backward-compat checks read
from prior runs.
"""

from __future__ import annotations

from typing import Literal

from engine.domain.finding import Severity
from pydantic import BaseModel, ConfigDict, Field

API_RESULT_SCHEMA_VERSION = "1"
API_SCHEMA_SNAPSHOT_VERSION = "1"

ApiCheckName = Literal[
    "contract",
    "negative",
    "auth",
    "latency",
    "pagination",
    "error_shape",
    "backward_compat",
]


class ApiIssue(BaseModel):
    """One discrete defect detected by an API check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(min_length=1, max_length=128)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=4000)
    method: str | None = Field(default=None, max_length=16)
    route: str | None = Field(default=None, max_length=2048)
    expected_status: int | None = Field(default=None, ge=100, le=599)
    observed_status: int | None = Field(default=None, ge=0, le=599)
    recommendation: str = Field(min_length=1, max_length=4000)
    evidence: dict[str, str] = Field(default_factory=dict)


class ApiCheckResult(BaseModel):
    """Result of one named check (contract / negative / auth / ...)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = API_RESULT_SCHEMA_VERSION
    check: ApiCheckName
    issues: tuple[ApiIssue, ...] = Field(default_factory=tuple)
    targets_scanned: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    skipped: bool = False
    skip_reason: str | None = Field(default=None, max_length=512)


class ApiRunOutcome(BaseModel):
    """Aggregated module-run state used by ``api/index.json``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = API_RESULT_SCHEMA_VERSION
    checks: tuple[ApiCheckResult, ...] = Field(default_factory=tuple)
    duration_ms: int = Field(ge=0)
    incomplete: bool = False
    openapi_loaded: bool = False
    graphql_loaded: bool = False


class ApiSchemaEndpoint(BaseModel):
    """One endpoint as captured in :class:`ApiSchemaSnapshot`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str = Field(min_length=1, max_length=16)
    path: str = Field(min_length=1, max_length=2048)
    required_request_fields: tuple[str, ...] = Field(default_factory=tuple)
    response_status_codes: tuple[int, ...] = Field(default_factory=tuple)
    required_response_fields: tuple[str, ...] = Field(default_factory=tuple)
    response_field_types: tuple[tuple[str, str], ...] = Field(default_factory=tuple)


class ApiSchemaSnapshot(BaseModel):
    """Wire format of ``api/api-schema.json`` (Phase 22.08 backward compat).

    Captures only the structural shape needed to detect breaking changes:
    endpoints, required fields, response statuses, and (for backwards
    diff) response field types. We deliberately omit descriptions /
    summaries / examples because they're not breaking.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = API_SCHEMA_SNAPSHOT_VERSION
    source: Literal["openapi", "graphql"]
    endpoints: tuple[ApiSchemaEndpoint, ...] = Field(default_factory=tuple)


__all__ = [
    "API_RESULT_SCHEMA_VERSION",
    "API_SCHEMA_SNAPSHOT_VERSION",
    "ApiCheckName",
    "ApiCheckResult",
    "ApiIssue",
    "ApiRunOutcome",
    "ApiSchemaEndpoint",
    "ApiSchemaSnapshot",
]
