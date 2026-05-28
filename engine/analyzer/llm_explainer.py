"""Analyzer LLM explainer adapter (task 09.05, ADR-0014).

Mirrors the planner's adapter shape: a :class:`Protocol`, a
:class:`NullLlmExplainer` default, and two HTTP-only provider
adapters. The explainer NEVER replaces the deterministic hypothesis —
it appends a one-sentence ``llm_refinement`` string. With the feature
flag off (default), every analyzer run is fully deterministic.

Budget enforcement reuses :func:`engine.planner.llm_adapter.estimate_cost_usd`
to keep the cost model consistent across LLM-bearing modules.
"""

from __future__ import annotations

import importlib.resources as resources
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engine.analyzer.models import (
    FailureClassification,
    FailureSignal,
    RootCauseHypothesis,
)
from engine.config.schema import AnalyzerLlmConfig
from engine.planner.llm_adapter import (
    BudgetExceededError,
    LlmUsage,
    ensure_within_budget,
    estimate_cost_usd,
)

PROMPT_VERSION: str = "1"
"""Bump when the locked prompt at ``llm_prompts/explainer.v1.md`` changes.

Version bumps require a new ADR per CLAUDE §34.
"""


class _RefinementEnvelope(BaseModel):
    """Strict envelope every provider response must satisfy."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    refinement: str = Field(default="", max_length=400)


class LlmExplainer(Protocol):
    """Protocol every analyzer LLM adapter must satisfy."""

    name: str

    @property
    def usage(self) -> LlmUsage:  # pragma: no cover - protocol stub
        ...

    def refine(
        self,
        signal: FailureSignal,
        classification: FailureClassification,
        hypothesis: RootCauseHypothesis,
    ) -> str | None:  # pragma: no cover - protocol stub
        ...


@dataclass
class NullLlmExplainer:
    """Default no-op adapter. Always returns ``None`` — analyzer keeps
    its deterministic hypothesis untouched."""

    name: str = "null"
    _usage: LlmUsage = field(default_factory=LlmUsage)

    @property
    def usage(self) -> LlmUsage:
        return self._usage

    def refine(
        self,
        signal: FailureSignal,
        classification: FailureClassification,
        hypothesis: RootCauseHypothesis,
    ) -> str | None:
        return None


def load_locked_prompt() -> str:
    """Read the locked prompt text. Raises if missing or empty."""

    pkg = resources.files("engine.analyzer.llm_prompts")
    body = pkg.joinpath(f"explainer.v{PROMPT_VERSION}.md").read_text(encoding="utf-8")
    if not body.strip():
        raise RuntimeError(
            "Locked explainer prompt is empty — refusing to call the LLM. "
            "Restore engine/analyzer/llm_prompts/explainer.v1.md."
        )
    return body


def build_signal_summary(
    signal: FailureSignal,
    classification: FailureClassification,
    hypothesis: RootCauseHypothesis,
) -> dict[str, Any]:
    """Build the sanitized payload sent to the provider.

    Only fields safe to share are included: titles, error names, status
    codes, step *names* (not values), and the deterministic
    classification/hypothesis. The summary is bounded — long fields are
    clipped — so a single signal never blows the token budget.
    """

    return {
        "test": {
            "title": signal.title[:200],
            "file": signal.file[:200],
            "status": signal.status,
            "duration_ms": signal.duration_ms,
            "retries": signal.retries,
            "module": signal.module,
            "fixture_failed": signal.fixture_failed,
        },
        "error": {
            "name": (signal.error_name or "")[:128],
            "message": (signal.error_message or "")[:400],
        },
        "evidence_count": len(signal.evidence),
        "network": [{"status": n.status_code, "url": n.url[:120]} for n in signal.network[:10]],
        "steps": [{"name": s.name[:120], "ok": s.ok} for s in signal.steps[:20]],
        "deterministic": {
            "category": classification.category,
            "confidence": classification.confidence,
            "hypothesis": hypothesis.hypothesis[:500],
            "rationale": classification.rationale[:300],
        },
    }


def parse_provider_response(raw: str) -> str:
    """Parse a provider response into a refinement string (may be ``''``)."""

    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc
    try:
        env = _RefinementEnvelope.model_validate(body)
    except ValidationError as exc:
        raise ValueError(f"LLM response did not match the locked envelope: {exc}") from exc
    return env.refinement


# ---------------------------------------------------------------------------
# Provider scaffolding
# ---------------------------------------------------------------------------


class ProviderConfigError(RuntimeError):
    """Raised when the configured provider is missing required setup."""


@dataclass
class _HttpExplainerState:
    config: AnalyzerLlmConfig
    _usage: LlmUsage = field(default_factory=LlmUsage)


class HttpLlmExplainerBase:
    """Shared base for HTTP-backed explainer providers."""

    name: str = "http-base"

    def __init__(
        self,
        *,
        config: AnalyzerLlmConfig,
        http_client: Any | None = None,
    ) -> None:
        self._state = _HttpExplainerState(config=config)
        self._http = http_client
        self._owns_http = http_client is None

    @property
    def usage(self) -> LlmUsage:
        return self._state._usage

    def refine(
        self,
        signal: FailureSignal,
        classification: FailureClassification,
        hypothesis: RootCauseHypothesis,
    ) -> str | None:
        budget = self._state.config.max_usd_per_run
        if self._state._usage.cost_usd >= budget:
            return None
        api_key = self._resolve_api_key()
        summary = build_signal_summary(signal, classification, hypothesis)
        prompt = load_locked_prompt()
        payload = self.build_payload(
            prompt=prompt,
            summary=summary,
            model=self._state.config.model,
        )

        estimated = estimate_cost_usd(
            input_tokens=_rough_tokens(prompt) + _rough_tokens(json.dumps(summary)),
            output_tokens=200,
        )
        try:
            ensure_within_budget(
                usage=self._state._usage,
                additional_cost=estimated,
                budget_usd=budget,
            )
        except BudgetExceededError:
            return None

        # Lazy import so httpx stays a soft dep at import time.
        import httpx

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
            refinement = parse_provider_response(text)
        except ValueError:
            self._record_usage(body=body, prompt_chars=len(prompt))
            return None
        self._record_usage(body=body, prompt_chars=len(prompt))
        return refinement or None

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
        summary: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:  # pragma: no cover - override
        raise NotImplementedError

    def extract_response_text(self, body: dict[str, Any]) -> str:  # pragma: no cover - override
        raise NotImplementedError

    def usage_from_response(
        self, body: dict[str, Any]
    ) -> tuple[int, int]:  # pragma: no cover - override
        return 0, 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_api_key(self) -> str:
        import os

        env_name = self._state.config.api_key_env
        if not env_name:
            raise ProviderConfigError(
                f"{self.name}: analyzer.llm.api_key_env is required when enabled=true."
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
    return max(1, chars // 4)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_llm_explainer(config: AnalyzerLlmConfig) -> LlmExplainer:
    """Return the configured adapter, or the null adapter when disabled."""

    if not config.enabled:
        return NullLlmExplainer()
    if config.provider == "openai":
        from engine.analyzer.llm_providers.openai_explainer import OpenAiLlmExplainer

        return OpenAiLlmExplainer(config=config)
    if config.provider == "anthropic":
        from engine.analyzer.llm_providers.anthropic_explainer import AnthropicLlmExplainer

        return AnthropicLlmExplainer(config=config)
    return NullLlmExplainer()


__all__ = [
    "BudgetExceededError",
    "HttpLlmExplainerBase",
    "LlmExplainer",
    "LlmUsage",
    "NullLlmExplainer",
    "PROMPT_VERSION",
    "ProviderConfigError",
    "build_llm_explainer",
    "build_signal_summary",
    "load_locked_prompt",
    "parse_provider_response",
]
