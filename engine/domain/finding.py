"""Finding entity (PRD §18.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.evidence import Evidence
from engine.domain.ids import validate_id
from engine.domain.schema import FINDINGS_SCHEMA_VERSION

Severity = Literal["critical", "high", "medium", "low", "info"]


class FindingLocation(SentinelModel):
    """Where in the app a finding was observed."""

    route: str | None = Field(default=None, max_length=2048)
    selector: str | None = Field(default=None, max_length=2048)
    file: str | None = Field(default=None, max_length=2048)
    line: int | None = Field(default=None, ge=0)


class Finding(SentinelModel):
    """A specific, evidence-backed defect observed during a run.

    Wire format aligned with PRD §18.2 (extended with the bookkeeping fields
    required by CLAUDE.md §24: ``run_id``, ``module``, ``confidence``,
    ``created_at``, ``schema_version``).
    """

    SCHEMA_VERSION: ClassVar[str] = FINDINGS_SCHEMA_VERSION

    id: str
    run_id: str
    module: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=128)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=8000)
    location: FindingLocation = Field(default_factory=FindingLocation)
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple)
    reproduction_steps: tuple[str, ...] = Field(default_factory=tuple)
    suggested_fix: str | None = Field(default=None, max_length=4000)
    affected_target: str | None = Field(default=None, max_length=2048)
    recommendation: str | None = Field(default=None, max_length=4000)
    cwe_id: str | None = Field(default=None, max_length=32, pattern=r"^CWE-\d+$")
    """Schema v2 (Phase 32): MITRE CWE identifier, e.g. ``CWE-347``."""
    attack_id: str | None = Field(default=None, max_length=32, pattern=r"^T\d{4}(\.\d{3})?$")
    """Schema v2 (Phase 32): MITRE ATT&CK technique id, e.g. ``T1606.001``."""
    owasp_api_id: str | None = Field(default=None, max_length=32, pattern=r"^API-\d{4}-\d{2}$")
    """Schema v2 (Phase 32): OWASP API Top-10 identifier, e.g. ``API-2023-01``."""
    created_at: datetime
    schema_version: str = Field(default=FINDINGS_SCHEMA_VERSION)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="FND")

    @field_validator("run_id")
    @classmethod
    def _check_run_id(cls, value: str) -> str:
        return validate_id(value, prefix="RUN")

    @field_validator("created_at")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Finding.created_at must be timezone-aware " "(use datetime.now(timezone.utc))."
            )
        return value.astimezone(UTC)

    def to_agent_message(self) -> dict[str, Any]:
        """Return the canonical agent-message dict (PRD §14.2, CLAUDE.md §15).

        Delegates to :func:`sentinelqa._agent_messages.finding_to_agent_message`
        so the SDK and the domain entity emit byte-equal dicts. Redaction
        is applied at the SDK layer.
        """

        from sentinelqa._agent_messages import finding_to_agent_message

        return finding_to_agent_message(self)


__all__ = ["Finding", "FindingLocation", "Severity"]
