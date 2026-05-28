"""SentinelQA planner module (PRD §9.2).

The planner consumes a :class:`engine.domain.DiscoveryGraph` and a
:class:`engine.domain.RiskMap` and emits a :class:`engine.domain.TestPlan`
that names every flow + test case the runner (Phase 08) will execute.

The MVP is a deterministic rules engine; an optional LLM adapter (Phase
06.04) can propose additional flows behind a feature flag.
"""

from __future__ import annotations

from engine.planner.core import (
    DeterministicPlanner,
    PlanningOutcome,
    bucketed_risk,
    priority_for_risk,
)
from engine.planner.llm_adapter import (
    PROMPT_VERSION,
    BudgetExceededError,
    LlmPlanner,
    LlmUsage,
    NullLlmPlanner,
    build_llm_planner,
)

__all__ = [
    "BudgetExceededError",
    "DeterministicPlanner",
    "LlmPlanner",
    "LlmUsage",
    "NullLlmPlanner",
    "PROMPT_VERSION",
    "PlanningOutcome",
    "bucketed_risk",
    "build_llm_planner",
    "priority_for_risk",
]
