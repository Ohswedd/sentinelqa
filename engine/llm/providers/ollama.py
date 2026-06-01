"""Ollama (local) provider (, ADR-0042).

Talks to a local Ollama server (default ``http://localhost:11434``) via
``httpx``. No API key — the adapter is the canonical "offline default".
If the server is unreachable, :meth:`complete` returns a graceful
:class:`LlmResponse` with ``available=False`` instead of raising; the
caller falls back to the deterministic path.

Structured output uses Ollama 0.5+'s ``format: <jsonschema>`` field.
Costs are always ``0.0`` (local compute).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx

from engine.llm.budget import LlmUsage
from engine.llm.protocol import LlmRequest, LlmResponse, ProviderHealth
from engine.llm.providers._http_base import HttpLlmProviderBase


@dataclass
class OllamaProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "ollama"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "qwen2.5-coder:7b"
    API_KEY_ENV: ClassVar[str] = ""  # no auth
    DEFAULT_TIMEOUT_SECONDS: ClassVar[float] = 60.0

    host: str = "http://localhost:11434"
    request_timeout_seconds: float = 60.0
    _last_models: tuple[str, ...] = field(default_factory=tuple)

    def endpoint_url(self) -> str:
        return f"{self.host.rstrip('/')}/api/chat"

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for msg in request.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or [{"role": "user", "content": "ping"}],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
            },
        }
        if request.response_schema is not None:
            payload["format"] = request.response_schema
        return payload

    def extract_response_text(self, body: dict[str, Any]) -> str:
        message = body.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        return "{}"

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        return int(body.get("prompt_eval_count", 0)), int(body.get("eval_count", 0))

    def cost_from_response(
        self,
        *,
        body: dict[str, Any],
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        return 0.0

    def _resolve_api_key(self) -> str:
        # Ollama has no API key. Return a sentinel; ``auth_headers`` ignores it.
        return ""

    def complete(self, request: LlmRequest) -> LlmResponse:
        """Override the base to handle unreachable-server gracefully.

        On any transport error (DNS, refused connection, timeout) we
        return an ``available=False`` response so the caller can fall
        back to the deterministic path. The base class raises an
        ``LlmTimeoutError`` instead — for Ollama we deliberately don't,
        because "offline default" semantics are part of the contract.
        """

        if self.rate_limit is not None:
            self.rate_limit.enforce(self.name)
        model = self.model or self.DEFAULT_MODEL
        payload = self.build_payload(request=request, model=model)

        client = self.http_client or httpx.Client(timeout=self.request_timeout_seconds)
        owns = self.http_client is None
        start = time.perf_counter()
        try:
            try:
                response = client.post(self.endpoint_url(), json=payload)
            except httpx.HTTPError:
                return LlmResponse(
                    text="",
                    parsed=None,
                    usage=self._usage,
                    cost_usd=0.0,
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    provider=self.name,
                    model=model,
                    available=False,
                )
        finally:
            if owns:
                client.close()
        latency_ms = (time.perf_counter() - start) * 1000.0

        if response.status_code == 404:
            return LlmResponse(
                text="",
                parsed=None,
                usage=self._usage,
                cost_usd=0.0,
                latency_ms=latency_ms,
                provider=self.name,
                model=model,
                available=False,
            )
        if response.status_code >= 400:
            return LlmResponse(
                text=response.text[:200],
                parsed=None,
                usage=self._usage,
                cost_usd=0.0,
                latency_ms=latency_ms,
                provider=self.name,
                model=model,
                available=False,
            )

        body = response.json()
        text = self.extract_response_text(body)
        parsed: dict[str, Any] | None = None
        if request.response_schema is not None:
            try:
                parsed = self._validate_structured_output(text, request.response_schema)
            except Exception:
                # Failed validation → available=True but parsed=None; caller decides.
                parsed = None

        input_tokens, output_tokens = self.usage_from_response(body)
        self._usage = self._usage.add(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,
        )
        return LlmResponse(
            text=text,
            parsed=parsed,
            usage=self._usage,
            cost_usd=0.0,
            latency_ms=latency_ms,
            provider=self.name,
            model=model,
            available=True,
        )

    def doctor(self) -> ProviderHealth:
        """Probe ``/api/tags`` for installed models, then check ours is present."""

        client = self.http_client or httpx.Client(timeout=self.request_timeout_seconds)
        owns = self.http_client is None
        start = time.perf_counter()
        try:
            try:
                response = client.get(f"{self.host.rstrip('/')}/api/tags")
            except httpx.HTTPError as exc:
                return ProviderHealth(
                    provider=self.name,
                    model=self.model or self.DEFAULT_MODEL,
                    status="unavailable",
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    detail=f"transport error: {type(exc).__name__}",
                )
        finally:
            if owns:
                client.close()
        latency_ms = (time.perf_counter() - start) * 1000.0

        if response.status_code != 200:
            return ProviderHealth(
                provider=self.name,
                model=self.model or self.DEFAULT_MODEL,
                status="unavailable",
                latency_ms=latency_ms,
                detail=f"HTTP {response.status_code}",
            )
        body = response.json()
        models = body.get("models") or []
        installed: list[str] = [
            entry.get("name", "")
            for entry in models
            if isinstance(entry, dict) and entry.get("name")
        ]
        self._last_models = tuple(installed)
        wanted = self.model or self.DEFAULT_MODEL
        if wanted in installed:
            return ProviderHealth(
                provider=self.name,
                model=wanted,
                status="available",
                latency_ms=latency_ms,
                detail=f"{len(installed)} model(s) installed",
            )
        return ProviderHealth(
            provider=self.name,
            model=wanted,
            status="degraded",
            latency_ms=latency_ms,
            detail=(
                f"model {wanted!r} not installed (run `ollama pull {wanted}`); "
                f"installed: {installed!r}"
            ),
        )


__all__ = ["OllamaProvider"]


# Silence unused-import for LlmUsage which is re-exported for tests.
_ = LlmUsage
