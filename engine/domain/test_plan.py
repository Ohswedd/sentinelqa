"""TestPlan entity (the documentation, §18.1).

A test plan packages every :class:`Flow` and :class:`TestCase` derived from
a :class:`DiscoveryGraph` for a single run. It is the wire format the
planner emits as ``plan.json`` and feeds the generator.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.flow import Flow
from engine.domain.ids import validate_id
from engine.domain.schema import CONFIG_SCHEMA_VERSION
from engine.domain.test_case import TestCase, TestModule

_COVERAGE_KEYS: frozenset[TestModule] = frozenset(
    {
        "functional",
        "a11y",
        "api",
        "performance",
        "visual",
        "security",
        "chaos",
        "llm_audit",
    }
)


class CoverageEstimate(SentinelModel):
    """Per-module estimate of how many planned test cases will execute.

    The estimate is an *intent* statement (how many cases were planned), not
    a guaranteed outcome. The runner / scoring modules ( / 14) own
    the actually-executed metric.
    """

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    by_module: dict[str, int] = Field(default_factory=dict)
    total: int = Field(default=0, ge=0)

    @field_validator("by_module")
    @classmethod
    def _validate_module_keys(cls, value: dict[str, int]) -> dict[str, int]:
        for key, count in value.items():
            if key not in _COVERAGE_KEYS:
                raise ValueError(f"coverage_estimate.by_module key {key!r} is not a known module.")
            if count < 0:
                raise ValueError(f"coverage_estimate.by_module[{key!r}] must be ≥ 0 (got {count}).")
        return value


class TestPlan(SentinelModel):
    """A complete test plan derived from discovery + risk."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    run_id: str
    discovery_graph_id: str
    risk_map_id: str
    target_url: str = Field(min_length=1, max_length=2048)
    flows: tuple[Flow, ...] = Field(default_factory=tuple)
    test_cases: tuple[TestCase, ...] = Field(default_factory=tuple)
    coverage_estimate: CoverageEstimate = Field(default_factory=CoverageEstimate)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="PLN")

    @field_validator("run_id")
    @classmethod
    def _check_run_id(cls, value: str) -> str:
        return validate_id(value, prefix="RUN")

    @field_validator("discovery_graph_id")
    @classmethod
    def _check_dg_id(cls, value: str) -> str:
        return validate_id(value, prefix="DG")

    @field_validator("risk_map_id")
    @classmethod
    def _check_rm_id(cls, value: str) -> str:
        return validate_id(value, prefix="RM")


__all__ = ["CoverageEstimate", "TestPlan"]
