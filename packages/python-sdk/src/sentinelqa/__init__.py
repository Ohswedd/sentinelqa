"""SentinelQA — the official Python SDK.

This is the **public** surface of SentinelQA. It is a typed, agent-friendly
facade over the engine (``engine.*``) and intentionally does NOT re-export
internal helpers; anything you can ``from sentinelqa import …`` is part of
the stable contract documented in our product spec

Importing this package is cheap: heavy submodules (orchestrator, planner,
discovery, generator, runner, reporter) are imported lazily by the
:class:`Sentinel` facade. ``import sentinelqa`` must stay under 200 ms so
agent-facing tooling (the documentation) starts quickly.
"""

from __future__ import annotations

from engine.domain import (
    AGENT_MESSAGE_SCHEMA_VERSION,
    FINDINGS_SCHEMA_VERSION,
    REPAIR_SUGGESTION_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCORE_SCHEMA_VERSION,
    Evidence,
    Finding,
    Flow,
    ModuleResult,
    RepairSuggestion,
    RiskMap,
    TestPlan,
)

from sentinelqa._errors import (
    ConfigError,
    DependencyMissingError,
    QualityGateFailedError,
    SentinelError,
    TestExecutionError,
    UnsafeTargetError,
)
from sentinelqa._facade import Sentinel
from sentinelqa._models import AuditResult, Policy, QualityGate

__all__ = [
    # SDK facade
    "Sentinel",
    # Run-shaped outputs
    "AuditResult",
    "Finding",
    "Evidence",
    "ModuleResult",
    "RepairSuggestion",
    # Planning + discovery outputs
    "TestPlan",
    "Flow",
    "RiskMap",
    # Policy + gating
    "QualityGate",
    "Policy",
    # Errors (also reachable via sentinelqa.errors)
    "SentinelError",
    "ConfigError",
    "UnsafeTargetError",
    "DependencyMissingError",
    "TestExecutionError",
    "QualityGateFailedError",
    # Schema versions — every public wire shape is versioned (the documentation).
    "RUN_SCHEMA_VERSION",
    "FINDINGS_SCHEMA_VERSION",
    "SCORE_SCHEMA_VERSION",
    "REPAIR_SUGGESTION_SCHEMA_VERSION",
    "AGENT_MESSAGE_SCHEMA_VERSION",
]


def _read_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("sentinelqa")
    except PackageNotFoundError:
        return "0.1.0"


__version__: str = _read_version()
