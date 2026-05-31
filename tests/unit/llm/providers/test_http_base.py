"""HttpLlmProviderBase — error-path coverage (timeout, doctor, helpers)."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import pytest
from engine.errors.base import LlmTimeoutError
from engine.llm import LlmBudget, LlmRequest
from engine.llm.protocol import ProviderHealth
from engine.llm.providers._http_base import HttpLlmProviderBase
from engine.llm.rate_limit import LlmRateLimit


class _DummyProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "dummy"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "dummy-1"
    API_KEY_ENV: ClassVar[str] = "DUMMY_API_KEY"
    ENDPOINT: ClassVar[str] = "https://dummy.example.com/v1/chat"

    def endpoint_url(self) -> str:
        return self.ENDPOINT

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        return {"model": model, "messages": [{"role": "user", "content": "ping"}]}

    def extract_response_text(self, body: dict[str, Any]) -> str:
        text = body.get("text", "")
        if isinstance(text, str):
            return text
        return ""

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        return int(body.get("in_t", 0)), int(body.get("out_t", 0))


def test_http_base_timeout_raises_llm_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _DummyProvider(http_client=client)
    with pytest.raises(LlmTimeoutError):
        provider.complete(LlmRequest(system="hi"))


def test_http_base_doctor_unavailable_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DUMMY_API_KEY", raising=False)
    health = _DummyProvider().doctor()
    assert isinstance(health, ProviderHealth)
    assert health.status == "unavailable"


def test_http_base_doctor_handles_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    health = _DummyProvider(http_client=client).doctor()
    assert health.status == "unavailable"
    assert "transport error" in health.detail


def test_http_base_doctor_degraded_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    health = _DummyProvider(http_client=client).doctor()
    assert health.status == "degraded"


def test_http_base_doctor_unavailable_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    health = _DummyProvider(http_client=client).doctor()
    assert health.status == "unavailable"


def test_http_base_budget_records_actual_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")
    budget = LlmBudget(max_usd_per_run=10.0)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "ok", "in_t": 100, "out_t": 50})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _DummyProvider(http_client=client, budget=budget)
    provider.complete(LlmRequest(system="hi", caller="planner"))
    usage = budget.usage_for("planner")
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cost_usd > 0


def test_http_base_rate_limit_consumes_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")
    limiter = LlmRateLimit(default_capacity=1, default_rate_per_minute=60.0)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _DummyProvider(http_client=client, rate_limit=limiter)
    provider.complete(LlmRequest(system="hi"))
    # Second call should trip the rate-limit gate.
    from engine.errors.base import LlmRateLimitedError

    with pytest.raises(LlmRateLimitedError):
        provider.complete(LlmRequest(system="hi"))


def test_http_base_validate_structured_output_rejects_non_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "not json", "in_t": 1, "out_t": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _DummyProvider(http_client=client)
    from engine.errors.base import LlmResponseValidationError

    with pytest.raises(LlmResponseValidationError):
        provider.complete(LlmRequest(system="hi", response_schema={"type": "object"}))


def test_http_base_validate_structured_output_rejects_non_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DUMMY_API_KEY", "key")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": '"a string"', "in_t": 1, "out_t": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _DummyProvider(http_client=client)
    from engine.errors.base import LlmResponseValidationError

    with pytest.raises(LlmResponseValidationError):
        provider.complete(LlmRequest(system="hi", response_schema={"type": "object"}))
