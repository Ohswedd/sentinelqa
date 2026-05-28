"""Shared HTTP scaffolding for LLM provider adapters.

Both OpenAI and Anthropic adapters speak HTTP+JSON, so we share an
``httpx.Client`` factory, retry/timeout policy, locked-prompt loading, and
the proposal→Flow conversion. The provider-specific subclasses only need
to know:

- which URL to POST,
- which auth header to attach,
- how to assemble the provider's request body around our locked prompt,
- how to extract the response text from the provider's response shape.

Vendor SDKs are deliberately *not* imported. Two reasons:

1. We don't want to pin SentinelQA to a vendor's release cadence.
2. Mocking ``httpx`` in tests is trivial; mocking a vendor SDK isn't.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from engine.config.schema import PlannerLlmConfig
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow
from engine.domain.ids import IdGenerator
from engine.domain.test_plan import TestPlan
from engine.planner.llm_adapter import (
    LlmUsage,
    build_graph_summary,
    ensure_within_budget,
    estimate_cost_usd,
    load_locked_prompt,
    parse_provider_response,
    proposals_to_flows,
)


class ProviderConfigError(RuntimeError):
    """Raised when the configured provider is missing required setup."""


@dataclass
class _HttpProviderState:
    config: PlannerLlmConfig
    _usage: LlmUsage = field(default_factory=LlmUsage)


class HttpLlmProviderBase:
    """Shared base for HTTP-backed planner providers.

    Subclasses override :meth:`endpoint_url`, :meth:`auth_headers`,
    :meth:`build_payload`, and :meth:`extract_response_text`.
    """

    name: str = "http-base"

    def __init__(
        self,
        *,
        config: PlannerLlmConfig,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._state = _HttpProviderState(config=config)
        self._http = http_client
        self._owns_http = http_client is None

    # ------------------------------------------------------------------
    # Public surface (matches LlmPlanner protocol)
    # ------------------------------------------------------------------

    @property
    def usage(self) -> LlmUsage:
        return self._state._usage

    def propose_flows(
        self,
        graph: DiscoveryGraph,
        base_plan: TestPlan,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        # Hard-stop if the budget is already exhausted.
        budget = self._state.config.max_usd_per_run
        if self._state._usage.cost_usd >= budget:
            return ()
        api_key = self._resolve_api_key()
        graph_summary = build_graph_summary(graph, base_plan)
        prompt = load_locked_prompt()
        payload = self.build_payload(
            prompt=prompt,
            graph_summary=graph_summary,
            max_proposals=self._state.config.max_proposals,
            model=self._state.config.model,
        )

        # Pre-flight cost estimate. We bound the worst case by the
        # configured max-proposals + the prompt size — exact tokens only
        # come back from the provider after the call.
        estimated = estimate_cost_usd(
            input_tokens=_rough_tokens(prompt) + _rough_tokens(json.dumps(graph_summary)),
            output_tokens=max(1, self._state.config.max_proposals) * 200,
        )
        ensure_within_budget(
            usage=self._state._usage,
            additional_cost=estimated,
            budget_usd=budget,
        )

        client = self._http or httpx.Client(
            timeout=self._state.config.request_timeout_seconds,
        )
        try:
            response = client.post(
                self.endpoint_url(),
                json=payload,
                headers=self.auth_headers(api_key=api_key),
            )
        finally:
            if self._owns_http and self._http is None:
                client.close()
        response.raise_for_status()

        body = response.json()
        text = self.extract_response_text(body)
        try:
            proposals = parse_provider_response(text)
        except ValueError:
            # Malformed response → record the cost but emit no flows.
            self._record_usage(body=body, prompt_chars=len(prompt))
            return ()

        existing_names = frozenset(f.name for f in base_plan.flows)
        flows = proposals_to_flows(
            proposals,
            graph=graph,
            id_generator=id_generator,
            existing_names=existing_names,
        )
        # Cap at max_proposals.
        if len(flows) > self._state.config.max_proposals:
            flows = flows[: self._state.config.max_proposals]
        self._record_usage(body=body, prompt_chars=len(prompt))
        return flows

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def endpoint_url(self) -> str:  # pragma: no cover - override
        raise NotImplementedError

    def auth_headers(self, *, api_key: str) -> dict[str, str]:  # pragma: no cover - override
        raise NotImplementedError

    def build_payload(
        self,
        *,
        prompt: str,
        graph_summary: dict[str, Any],
        max_proposals: int,
        model: str,
    ) -> dict[str, Any]:  # pragma: no cover - override
        raise NotImplementedError

    def extract_response_text(self, body: dict[str, Any]) -> str:  # pragma: no cover - override
        raise NotImplementedError

    def usage_from_response(
        self, body: dict[str, Any]
    ) -> tuple[int, int]:  # pragma: no cover - override
        """Return ``(input_tokens, output_tokens)`` from the provider response."""

        return 0, 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_api_key(self) -> str:
        env_name = self._state.config.api_key_env
        if not env_name:
            raise ProviderConfigError(
                f"{self.name}: planner.llm.api_key_env is required when enabled=true."
            )
        api_key = os.environ.get(env_name)
        if not api_key:
            raise ProviderConfigError(
                f"{self.name}: env var {env_name!r} is not set; cannot call the provider."
            )
        return api_key

    def _record_usage(self, *, body: dict[str, Any], prompt_chars: int) -> None:
        input_tokens, output_tokens = self.usage_from_response(body)
        if input_tokens == 0:
            input_tokens = _rough_tokens_from_chars(prompt_chars)
        if output_tokens == 0:
            output_tokens = 200
        cost = estimate_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        self._state._usage = self._state._usage.add(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


def _rough_tokens(text: str) -> int:
    return _rough_tokens_from_chars(len(text))


def _rough_tokens_from_chars(chars: int) -> int:
    # Vendor-agnostic, deliberately conservative.
    return max(1, chars // 4)


__all__ = [
    "HttpLlmProviderBase",
    "ProviderConfigError",
]
