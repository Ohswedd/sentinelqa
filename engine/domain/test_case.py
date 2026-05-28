"""TestCase entity (PRD §18.1)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

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

TestModule = Literal[
    "functional",
    "a11y",
    "api",
    "performance",
    "visual",
    "security",
    "chaos",
    "llm_audit",
]

# Map test_type → the module that owns its execution. `regression` is the
# only test_type that isn't a module name; we route it to functional.
_TYPE_TO_MODULE: dict[TestType, TestModule] = {
    "functional": "functional",
    "a11y": "a11y",
    "api": "api",
    "performance": "performance",
    "visual": "visual",
    "security": "security",
    "chaos": "chaos",
    "llm_audit": "llm_audit",
    "regression": "functional",
}


class TestCase(SentinelModel):
    """One generated Playwright test bound to a :class:`Flow`."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    flow_id: str
    file_path: Path
    test_type: TestType = "functional"
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    module: TestModule | None = None

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="TC")

    @field_validator("flow_id")
    @classmethod
    def _check_flow_id(cls, value: str) -> str:
        return validate_id(value, prefix="FLW")

    @model_validator(mode="after")
    def _default_module_from_type(self) -> TestCase:
        if self.module is None:
            object.__setattr__(self, "module", _TYPE_TO_MODULE[self.test_type])
        return self


__all__ = ["TestCase", "TestModule", "TestType"]
