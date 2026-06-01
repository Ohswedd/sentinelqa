"""SentinelQA core domain models (our product spec, our engineering rules).

Every later engine sub-package imports its entities from here. Models are
frozen Pydantic v2 models that forbid unknown fields, so they can safely be
shared across module/process boundaries and serialized into the run
artifact tree (the documentation) without losing typing.

The public surface is what `from engine.domain import X` exposes via
``__all__``. Internal helpers (``SentinelModel`` base, ID generator,
JSON-schema dumper) are imported via their own modules.
"""

from __future__ import annotations

from engine.domain.api_endpoint import ApiEndpoint, ApiEndpointSource
from engine.domain.base import SentinelModel
from engine.domain.discovery_graph import AuthBoundary, DiscoveryGraph
from engine.domain.element import Element
from engine.domain.evidence import Evidence, EvidenceType
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.flow import Flow, FlowSource, FlowStep, Priority, Risk
from engine.domain.form import Form, FormField
from engine.domain.ids import IdGenerator, validate_id
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.project import Framework, PackageManager, Project
from engine.domain.quality_score import QualityScore
from engine.domain.repair_suggestion import RepairSuggestion
from engine.domain.risk_map import RiskMap, RouteRisk
from engine.domain.route import Route
from engine.domain.schema import (
    AGENT_MESSAGE_SCHEMA_VERSION,
    CONFIG_SCHEMA_VERSION,
    FINDINGS_SCHEMA_VERSION,
    REPAIR_SUGGESTION_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCORE_SCHEMA_VERSION,
)
from engine.domain.target import Mode, Target
from engine.domain.test_case import TestCase, TestModule, TestType
from engine.domain.test_plan import CoverageEstimate, TestPlan
from engine.domain.test_run import RunStatus, TestRun

__all__ = [
    # Base + IDs + schema versions
    "SentinelModel",
    "IdGenerator",
    "validate_id",
    "RUN_SCHEMA_VERSION",
    "FINDINGS_SCHEMA_VERSION",
    "SCORE_SCHEMA_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "REPAIR_SUGGESTION_SCHEMA_VERSION",
    "AGENT_MESSAGE_SCHEMA_VERSION",
    # Entities
    "Project",
    "Framework",
    "PackageManager",
    "Target",
    "Mode",
    "Route",
    "Element",
    "Form",
    "FormField",
    "ApiEndpoint",
    "ApiEndpointSource",
    "Flow",
    "FlowSource",
    "FlowStep",
    "Priority",
    "Risk",
    "TestCase",
    "TestModule",
    "TestType",
    "TestPlan",
    "CoverageEstimate",
    "TestRun",
    "RunStatus",
    "ModuleResult",
    "ModuleStatus",
    "Finding",
    "FindingLocation",
    "Severity",
    "Evidence",
    "EvidenceType",
    "QualityScore",
    "PolicyDecision",
    "ReleaseDecision",
    "RepairSuggestion",
    "DiscoveryGraph",
    "AuthBoundary",
    "RiskMap",
    "RouteRisk",
]
