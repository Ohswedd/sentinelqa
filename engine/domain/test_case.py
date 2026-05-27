"""TestCase entity (PRD §18.1)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import CONFIG_SCHEMA_VERSION

TestType = Literal[
    "functional",
    "a11y",
    "api",
    "performance",
    "visual",
    "security",
    "chaos",
    "llm_audit",
    "regression",
]


class TestCase(SentinelModel):
    """One generated Playwright test bound to a :class:`Flow`."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    flow_id: str
    file_path: Path
    test_type: TestType = "functional"
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="TC")

    @field_validator("flow_id")
    @classmethod
    def _check_flow_id(cls, value: str) -> str:
        return validate_id(value, prefix="FLW")


__all__ = ["TestCase", "TestType"]
