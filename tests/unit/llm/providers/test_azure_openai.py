"""AzureOpenAiProvider — api-key header form + per-deployment URL."""

from __future__ import annotations

import httpx
import pytest
from engine.errors.base import (
    LlmMissingKeyError,
    LlmRequestRejectedError,
    LlmResponseValidationError,
)
from engine.llm import LlmRequest
from engine.llm.providers.azure_openai import AzureOpenAiProvider


def _azure_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
        "model": "gpt-4o-mini",
    }


def test_azure_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test")
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=_azure_body('{"ok": true}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AzureOpenAiProvider(
        resource="myresource",
        deployment="gpt4o-prod",
        api_version="2024-08-01-preview",
        http_client=client,
    )
    response = provider.complete(
        LlmRequest(
            system="hi",
            messages=({"role": "user", "content": "ping"},),
            response_schema={"type": "object", "required": ["ok"]},
        )
    )
    assert response.available is True
    assert response.parsed == {"ok": True}
    sent = captured[0]
    # Critical: api-key header form, NOT Authorization Bearer.
    assert sent.headers["api-key"] == "azure-test"
    assert "authorization" not in {h.lower() for h in sent.headers}
    # URL contains the deployment path + api-version query.
    assert "myresource.openai.azure.com" in str(sent.url)
    assert "gpt4o-prod" in str(sent.url)
    assert "api-version=2024-08-01-preview" in str(sent.url)


def test_azure_404_on_unknown_deployment_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "deployment not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AzureOpenAiProvider(
        resource="r",
        deployment="d",
        http_client=client,
    )
    with pytest.raises(LlmRequestRejectedError):
        provider.complete(LlmRequest(system="ping"))


def test_azure_401_raises_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "wrong")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AzureOpenAiProvider(resource="r", deployment="d", http_client=client)
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_azure_schema_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_azure_body('{"wrong_key": 1}'))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AzureOpenAiProvider(resource="r", deployment="d", http_client=client)
    with pytest.raises(LlmResponseValidationError):
        provider.complete(
            LlmRequest(
                system="",
                response_schema={"type": "object", "required": ["ok"]},
            )
        )


def test_azure_endpoint_url_requires_resource_and_deployment() -> None:
    provider = AzureOpenAiProvider()  # no resource / deployment
    with pytest.raises(ValueError):
        provider.endpoint_url()
