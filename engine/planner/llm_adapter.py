"""Planner LLM adapter (task 06.04, ADR-0011).

The deterministic planner ships in Phase 06; this adapter lets an LLM
*propose* additional flows behind a feature flag. Default is the
:class:`NullLlmPlanner` — planning works without any API key, in CI, and
in air-gapped environments.

Every proposal is re-parsed through Pydantic; malformed proposals are
dropped without failing the run. A per-run USD budget bounds spend; the
adapter falls back to deterministic-only when exceeded.
"""

from __future__ import annotations

import importlib.resources as resources
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engine.config.schema import PlannerLlmConfig
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow, FlowStep, Priority, Risk
from engine.domain.ids import IdGenerator
from engine.domain.test_plan import TestPlan

PROMPT_VERSION: str = "1"
"""Bump when the locked prompt at ``llm_prompts/planner.v1.md`` changes.

Version bumps require a new ADR per CLAUDE §34.
"""

# Per-1k-token prices (USD). These are deliberately conservative; the
# adapter is allowed to refuse a request whose worst-case cost exceeds
# the configured budget.
_DEFAULT_PRICE_PER_1K_INPUT: float = 0.003
_DEFAULT_PRICE_PER_1K_OUTPUT: float = 0.015


@dataclass(frozen=True)
class LlmUsage:
    """Tracks token + cost usage across an adapter's lifetime."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0

    def add(self, *, input_tokens: int, output_tokens: int, cost_usd: float) -> LlmUsage:
        return LlmUsage(
            input_tokens=self.input_tokens + input_tokens,
            output_tokens=self.output_tokens + output_tokens,
            cost_usd=self.cost_usd + cost_usd,
            requests=self.requests + 1,
        )


class BudgetExceededError(RuntimeError):
    """Raised when the configured per-run USD budget is exhausted."""


class _ProposalStep(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=1, max_length=2000)
    expected_outcome: str = Field(min_length=1, max_length=2000)


class _ProposalFlow(BaseModel):
    """Strict validator for one LLM-proposed flow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: Priority = "P2"
    risk: Risk = "medium"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    target_route_path: str | None = Field(default=None, max_length=2048)
    steps: list[_ProposalStep] = Field(default_factory=list, min_length=1, max_length=12)
    required_auth_role: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=16)


class _ProposalEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flows: list[_ProposalFlow] = Field(default_factory=list, max_length=64)


class LlmPlanner(Protocol):
    """Protocol every planner LLM adapter must satisfy."""

    name: str

    @property
    def usage(self) -> LlmUsage:  # pragma: no cover - protocol stub
        ...

    def propose_flows(
        self,
        graph: DiscoveryGraph,
        base_plan: TestPlan,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:  # pragma: no cover - protocol stub
        ...


@dataclass
class NullLlmPlanner:
    """Default no-op adapter. Returns no proposals, costs nothing.

    Used in CI, with the feature flag off, and when no API key is set.
    """

    name: str = "null"
    _usage: LlmUsage = field(default_factory=LlmUsage)

    @property
    def usage(self) -> LlmUsage:
        return self._usage

    def propose_flows(
        self,
        graph: DiscoveryGraph,
        base_plan: TestPlan,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        return ()


def load_locked_prompt() -> str:
    """Read the locked prompt text. Raises if missing or empty."""

    pkg = resources.files("engine.planner.llm_prompts")
    body = pkg.joinpath(f"planner.v{PROMPT_VERSION}.md").read_text(encoding="utf-8")
    if not body.strip():
        raise RuntimeError(
            "Locked planner prompt is empty — refusing to call the LLM. "
            "Restore engine/planner/llm_prompts/planner.v1.md."
        )
    return body


def build_graph_summary(graph: DiscoveryGraph, base_plan: TestPlan) -> dict[str, Any]:
    """Build the sanitized payload sent to the LLM (no PII / no secrets)."""

    return {
        "routes": [
            {"path": route.path, "auth_required": bool(route.auth_required)}
            for route in graph.routes
        ],
        "forms_count": len(graph.forms),
        "api_endpoints_count": len(graph.api_endpoints),
        "auth_boundaries_count": len(graph.auth_boundaries),
        "existing_flow_names": sorted({f.name for f in base_plan.flows}),
    }


def parse_provider_response(raw: str) -> tuple[_ProposalFlow, ...]:
    """Parse an LLM response into validated proposals.

    Malformed envelopes raise :class:`ValueError`; the caller turns that
    into an empty proposal list (CLAUDE §32 — typed errors are actionable).
    """

    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc
    try:
        envelope = _ProposalEnvelope.model_validate(body)
    except ValidationError as exc:
        raise ValueError(f"LLM response did not match the locked envelope: {exc}") from exc
    return tuple(envelope.flows)


def proposals_to_flows(
    proposals: Iterable[_ProposalFlow],
    *,
    graph: DiscoveryGraph,
    id_generator: IdGenerator,
    existing_names: frozenset[str],
) -> tuple[Flow, ...]:
    """Convert validated proposals → typed :class:`Flow` records.

    Proposals are dropped (never raise) when:

    - The flow name collides with an existing deterministic flow.
    - ``target_route_path`` is non-null but doesn't match any route.
    - Any step fails Pydantic validation.
    """

    route_by_path = {route.path: route for route in graph.routes}
    out: list[Flow] = []
    for proposal in proposals:
        if proposal.name in existing_names:
            continue
        route = None
        if proposal.target_route_path is not None:
            route = route_by_path.get(proposal.target_route_path)
            if route is None:
                continue
        try:
            steps = tuple(
                FlowStep(
                    description=step.description,
                    expected_outcome=step.expected_outcome,
                    target_route_id=route.id if route else None,
                )
                for step in proposal.steps
            )
            flow = Flow(
                id=id_generator.new("FLW"),
                name=proposal.name,
                description=proposal.description,
                steps=steps,
                priority=proposal.priority,
                risk=proposal.risk,
                confidence=proposal.confidence,
                required_auth_role=proposal.required_auth_role,
                extractor=f"llm.v{PROMPT_VERSION}",
                source="llm",
                tags=("llm", *proposal.tags),
            )
        except ValidationError:
            continue
        out.append(flow)
    return tuple(out)


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    price_per_1k_input: float = _DEFAULT_PRICE_PER_1K_INPUT,
    price_per_1k_output: float = _DEFAULT_PRICE_PER_1K_OUTPUT,
) -> float:
    """Token-based cost estimate. Both prices are USD per 1k tokens."""

    return (input_tokens / 1000.0) * price_per_1k_input + (
        output_tokens / 1000.0
    ) * price_per_1k_output


def ensure_within_budget(
    *,
    usage: LlmUsage,
    additional_cost: float,
    budget_usd: float,
) -> None:
    """Raise :class:`BudgetExceededError` if the next request would exceed budget."""

    projected = usage.cost_usd + additional_cost
    if projected > budget_usd:
        raise BudgetExceededError(
            f"LLM cost projected {projected:.4f} USD exceeds budget {budget_usd:.4f} USD. "
            "Falling back to deterministic-only planning."
        )


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------


def build_llm_planner(config: PlannerLlmConfig) -> LlmPlanner:
    """Return the configured adapter, or the null adapter when disabled.

    Provider construction is lazy: the OpenAI / Anthropic adapters are
    only imported when their respective provider is selected, so the SDK
    dependencies stay optional.
    """

    if not config.enabled:
        return NullLlmPlanner()
    if config.provider == "openai":
        from engine.planner.llm_providers.openai_planner import OpenAiLlmPlanner

        return OpenAiLlmPlanner(config=config)
    if config.provider == "anthropic":
        from engine.planner.llm_providers.anthropic_planner import AnthropicLlmPlanner

        return AnthropicLlmPlanner(config=config)
    return NullLlmPlanner()


PROMPT_PATH_FOR_TESTS: Path = (
    Path(__file__).parent / "llm_prompts" / f"planner.v{PROMPT_VERSION}.md"
)


__all__ = [
    "PROMPT_VERSION",
    "BudgetExceededError",
    "LlmPlanner",
    "LlmUsage",
    "NullLlmPlanner",
    "build_graph_summary",
    "build_llm_planner",
    "ensure_within_budget",
    "estimate_cost_usd",
    "load_locked_prompt",
    "parse_provider_response",
    "proposals_to_flows",
]
