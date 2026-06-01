"""Shared HTTP scaffolding for canonical :class:`LlmProvider` adapters.

Every Phase-30 adapter speaks HTTP+JSON via ``httpx``. The shared base
encapsulates:

- API-key lookup from an env var (never inlined; our engineering rules).
- Structured-output enforcement (server-side hint + client-side
  re-validation against the request's ``response_schema``).
- Latency timing.
- Token-bucket rate-limit enforcement (via :class:`LlmRateLimit`).
- Optional :class:`LlmBudget` integration when wired up by the caller.

Concrete subclasses override:

- :meth:`endpoint_url`            — final POST URL.
- :meth:`auth_headers`            — provider-specific auth headers.
- :meth:`build_payload`           — request body.
- :meth:`extract_response_text`   — pull the model output text.
- :meth:`usage_from_response`     — pull (input_tokens, output_tokens).
- :meth:`cost_from_response`      — optional override when the provider
                                     returns its own cost number
                                     (e.g. OpenRouter).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx

from engine.errors.base import (
    LlmMissingKeyError,
    LlmRateLimitedError,
    LlmRequestRejectedError,
    LlmResponseValidationError,
    LlmTimeoutError,
)
from engine.llm.budget import LlmBudget, LlmUsage, estimate_cost_usd
from engine.llm.protocol import LlmRequest, LlmResponse, ProviderHealth
from engine.llm.rate_limit import LlmRateLimit


@dataclass
class HttpLlmProviderBase:
    """Shared base for canonical HTTP-based LLM providers.

    Concrete subclasses are still dataclasses (so they're cheap to
    instantiate from the registry); they override the hook methods.
    """

    name: ClassVar[str] = "http-base"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = ""
    API_KEY_ENV: ClassVar[str] = ""
    DEFAULT_TIMEOUT_SECONDS: ClassVar[float] = 30.0

    model: str = ""
    api_key_env: str | None = None
    request_timeout_seconds: float = 30.0
    budget: LlmBudget | None = None
    rate_limit: LlmRateLimit | None = None
    http_client: httpx.Client | None = None
    _usage: LlmUsage = field(default_factory=LlmUsage)

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def complete(self, request: LlmRequest) -> LlmResponse:
        if self.rate_limit is not None:
            self.rate_limit.enforce(self.name)

        api_key = self._resolve_api_key()
        model = self.model or self.DEFAULT_MODEL
        payload = self.build_payload(request=request, model=model)

        if self.budget is not None:
            estimated = self._estimate_cost(request)
            self.budget.pre_check(
                caller=request.caller,
                estimated_cost_usd=estimated,
            )

        client = self.http_client or httpx.Client(
            timeout=self.request_timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS,
        )
        owns_client = self.http_client is None
        start = time.perf_counter()
        try:
            try:
                response = client.post(
                    self.endpoint_url(),
                    json=payload,
                    headers=self.auth_headers(api_key=api_key),
                )
            except httpx.TimeoutException as exc:
                raise LlmTimeoutError(
                    provider=self.name,
                    timeout_seconds=self.request_timeout_seconds,
                ) from exc
        finally:
            if owns_client:
                client.close()
        latency_ms = (time.perf_counter() - start) * 1000.0

        status = response.status_code
        if status == 401:
            raise LlmMissingKeyError(
                provider=self.name,
                env_var=self.api_key_env or self.API_KEY_ENV,
            )
        if status == 429:
            raise LlmRateLimitedError(provider=self.name)
        if status >= 400:
            raise LlmRequestRejectedError(
                provider=self.name,
                status_code=status,
                detail=response.text[:200],
            )

        body = response.json()
        text = self.extract_response_text(body)

        parsed: dict[str, Any] | None = None
        if request.response_schema is not None:
            parsed = self._validate_structured_output(text, request.response_schema)

        input_tokens, output_tokens = self.usage_from_response(body)
        cost = self.cost_from_response(
            body=body,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        if self.budget is not None:
            self.budget.add(
                caller=request.caller,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )
        self._usage = self._usage.add(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

        return LlmResponse(
            text=text,
            parsed=parsed,
            usage=self._usage,
            cost_usd=cost,
            latency_ms=latency_ms,
            provider=self.name,
            model=model,
            available=True,
        )

    def doctor(self) -> ProviderHealth:
        """Default probe: a 1-token ping. Subclasses override when their
        endpoint has a cheaper health check (Ollama exposes ``/api/tags``)."""

        try:
            api_key = self._resolve_api_key()
        except LlmMissingKeyError:
            return ProviderHealth(
                provider=self.name,
                model=self.model or self.DEFAULT_MODEL,
                status="unavailable",
                latency_ms=0.0,
                detail=f"env var {self.api_key_env or self.API_KEY_ENV!r} is not set",
            )

        probe = LlmRequest(
            system="ping",
            messages=({"role": "user", "content": "ping"},),
            response_schema=None,
            max_output_tokens=1,
            temperature=0.0,
            caller="doctor",
        )
        model = self.model or self.DEFAULT_MODEL
        payload = self.build_payload(request=probe, model=model)
        client = self.http_client or httpx.Client(timeout=self.request_timeout_seconds)
        owns_client = self.http_client is None
        start = time.perf_counter()
        try:
            try:
                response = client.post(
                    self.endpoint_url(),
                    json=payload,
                    headers=self.auth_headers(api_key=api_key),
                )
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                return ProviderHealth(
                    provider=self.name,
                    model=model,
                    status="unavailable",
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    detail=f"transport error: {type(exc).__name__}",
                )
        finally:
            if owns_client:
                client.close()
        latency_ms = (time.perf_counter() - start) * 1000.0
        if 200 <= response.status_code < 300:
            return ProviderHealth(
                provider=self.name,
                model=model,
                status="available",
                latency_ms=latency_ms,
                detail="ok",
            )
        if response.status_code in {401, 403}:
            return ProviderHealth(
                provider=self.name,
                model=model,
                status="unavailable",
                latency_ms=latency_ms,
                detail=f"auth rejected: HTTP {response.status_code}",
            )
        return ProviderHealth(
            provider=self.name,
            model=model,
            status="degraded",
            latency_ms=latency_ms,
            detail=f"HTTP {response.status_code}",
        )

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def endpoint_url(self) -> str:  # pragma: no cover - override
        raise NotImplementedError

    def auth_headers(self, *, api_key: str) -> dict[str, str]:  # pragma: no cover - override
        raise NotImplementedError

    def build_payload(
        self,
        *,
        request: LlmRequest,
        model: str,
    ) -> dict[str, Any]:  # pragma: no cover - override
        raise NotImplementedError

    def extract_response_text(self, body: dict[str, Any]) -> str:  # pragma: no cover - override
        raise NotImplementedError

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        """Default: return (0, 0). Subclasses override."""

        return 0, 0

    def cost_from_response(
        self,
        *,
        body: dict[str, Any],
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Default: token-rate estimate. OpenRouter overrides to read
        ``usage.cost`` from the body verbatim."""

        return estimate_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_api_key(self) -> str:
        env_name = self.api_key_env or self.API_KEY_ENV
        if not env_name:
            raise LlmMissingKeyError(provider=self.name, env_var="<not configured>")
        api_key = os.environ.get(env_name)
        if not api_key:
            raise LlmMissingKeyError(provider=self.name, env_var=env_name)
        return api_key

    def _estimate_cost(self, request: LlmRequest) -> float:
        prompt_chars = len(request.system) + sum(
            len(m.get("content", "")) for m in request.messages
        )
        # 4 chars ≈ 1 token (vendor-agnostic, conservative).
        input_tokens = max(1, prompt_chars // 4)
        output_tokens = max(1, request.max_output_tokens)
        return estimate_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _validate_structured_output(
        self,
        text: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            body = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LlmResponseValidationError(
                provider=self.name,
                detail=f"response was not valid JSON: {exc}",
            ) from exc
        if not isinstance(body, dict):
            raise LlmResponseValidationError(
                provider=self.name,
                detail="response was valid JSON but not an object",
            )
        # Lightweight client-side schema check: every required top-level
        # property must be present. Full draft-2020-12 validation lives
        # in the caller (Phase 06 _ProposalEnvelope etc.) — this is a
        # provider-side belt for the suspenders.
        if "required" in schema:
            required = schema.get("required") or []
            missing = [k for k in required if k not in body]
            if missing:
                raise LlmResponseValidationError(
                    provider=self.name,
                    detail=f"missing required top-level keys: {missing!r}",
                )
        return body


__all__ = ["HttpLlmProviderBase"]
