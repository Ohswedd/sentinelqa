"""ModuleResult entity."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.finding import Finding
from engine.domain.ids import validate_id
from engine.domain.schema import RUN_SCHEMA_VERSION

ModuleStatus = Literal["passed", "failed", "skipped", "errored", "incomplete"]


class ModuleResult(SentinelModel):
    """The result of one module's contribution to a run."""

    SCHEMA_VERSION: ClassVar[str] = RUN_SCHEMA_VERSION

    id: str
    name: str = Field(min_length=1, max_length=64)
    status: ModuleStatus
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    metrics: dict[str, float | int] = Field(default_factory=dict)
    duration_ms: int = Field(ge=0)
    errors: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="MOD")

    def to_dict(self) -> dict[str, Any]:
        # Override to keep findings ordered deterministically by ID — Phase
        # 14 scoring depends on a stable iteration order.
        payload = super().to_dict()
        if isinstance(payload.get("findings"), list):
            payload["findings"] = sorted(payload["findings"], key=lambda f: f["id"])
        return payload


__all__ = ["ModuleResult", "ModuleStatus"]
