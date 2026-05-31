"""Doctor / error / fallback coverage across every provider.

Each test pins a single un-exercised branch from the per-file coverage
report so engine.llm hits the phase-30 ≥ 90% per-file floor.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from engine.errors.base import LlmRequestRejectedError
from engine.llm import LlmRequest
from engine.llm.providers.azure_openai import AzureOpenAiProvider
from engine.llm.providers.gemini import GeminiProvider
from engine.llm.providers.groq import GroqProvider
from engine.llm.providers.mistral import MistralProvider
from engine.llm.providers.ollama import OllamaProvider
from engine.llm.providers.openrouter import OpenRouterProvider
from engine.llm.providers.vertex import VertexAiProvider


def _stub_handler(status: int = 200, body: dict[str, Any] | None = None) -> Any:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body or {})

    return handler


# ------------------------------------------------------------------
# Gemini: doctor 401 / transport error / unknown-model cost fallback
# ------------------------------------------------------------------


def test_gemini_doctor_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "bad")

    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(401, {})))
    health = GeminiProvider(http_client=client).doctor()
    assert health.status == "unavailable"


def test_gemini_doctor_degraded_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "ok")

    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(500, {})))
    health = GeminiProvider(http_client=client).doctor()
    assert health.status == "degraded"


def test_gemini_doctor_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "ok")

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    health = GeminiProvider(http_client=client).doctor()
    assert health.status == "unavailable"


def test_gemini_cost_unknown_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "ok")

    body = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 1000},
    }
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(200, body)))
    provider = GeminiProvider(model="gemini-future", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0  # fell back to default rates


def test_gemini_extract_returns_empty_on_no_candidates() -> None:
    p = GeminiProvider()
    assert p.extract_response_text({}) == "{}"
    assert p.extract_response_text({"candidates": []}) == "{}"
    assert p.extract_response_text({"candidates": [{"content": {"parts": []}}]}) == "{}"


# ------------------------------------------------------------------
# Groq: extract fallback + unknown-model cost + 5xx
# ------------------------------------------------------------------


def test_groq_unknown_model_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g")

    body = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(200, body)))
    provider = GroqProvider(model="future-model", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0


def test_groq_extract_no_choices() -> None:
    p = GroqProvider()
    assert p.extract_response_text({}) == "{}"
    assert p.extract_response_text({"choices": [{"message": {"content": None}}]}) == "{}"


def test_groq_500_raises_request_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g")

    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(500, {})))
    with pytest.raises(LlmRequestRejectedError):
        GroqProvider(http_client=client).complete(LlmRequest(system="ping"))


# ------------------------------------------------------------------
# Mistral: unknown-model cost + extract no-choices + 5xx
# ------------------------------------------------------------------


def test_mistral_unknown_model_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "m")

    body = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(200, body)))
    provider = MistralProvider(model="future-model", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0


def test_mistral_extract_no_choices() -> None:
    p = MistralProvider()
    assert p.extract_response_text({}) == "{}"
    assert p.extract_response_text({"choices": [{"message": {"content": None}}]}) == "{}"


def test_mistral_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(500, {})))
    with pytest.raises(LlmRequestRejectedError):
        MistralProvider(http_client=client).complete(LlmRequest(system="ping"))


# ------------------------------------------------------------------
# Ollama: extract empty + 5xx → available=False + structured no-schema
# ------------------------------------------------------------------


def test_ollama_extract_no_message() -> None:
    p = OllamaProvider()
    assert p.extract_response_text({}) == "{}"
    assert p.extract_response_text({"message": {}}) == "{}"
    assert p.extract_response_text({"message": {"content": None}}) == "{}"


def test_ollama_500_returns_available_false() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(500, {"err": "x"})))
    provider = OllamaProvider(http_client=client)
    response = provider.complete(LlmRequest(system="ping"))
    assert response.available is False


def test_ollama_cost_is_zero_for_unknown_model(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "message": {"content": "ok"},
        "prompt_eval_count": 100,
        "eval_count": 50,
    }
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(200, body)))
    provider = OllamaProvider(model="anything", http_client=client)
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd == 0.0  # local always free


# ------------------------------------------------------------------
# OpenRouter: 5xx + extract empty + zero usage.cost (falls back)
# ------------------------------------------------------------------


def test_openrouter_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(500, {})))
    with pytest.raises(LlmRequestRejectedError):
        OpenRouterProvider(http_client=client).complete(LlmRequest(system="ping"))


def test_openrouter_extract_no_choices() -> None:
    p = OpenRouterProvider()
    assert p.extract_response_text({}) == "{}"


def test_openrouter_zero_cost_in_usage_uses_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    body = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.0},
    }
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(200, body)))
    response = OpenRouterProvider(http_client=client).complete(LlmRequest(system=""))
    # Provider trusts the zero — does NOT fall back.
    assert response.cost_usd == 0.0


# ------------------------------------------------------------------
# Azure: unknown-model cost fallback + extract no-choices
# ------------------------------------------------------------------


def test_azure_unknown_model_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "a")

    body = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    client = httpx.Client(transport=httpx.MockTransport(_stub_handler(200, body)))
    provider = AzureOpenAiProvider(
        resource="r",
        deployment="d",
        model="custom-deployment",
        http_client=client,
    )
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0


def test_azure_extract_no_choices() -> None:
    p = AzureOpenAiProvider()
    assert p.extract_response_text({}) == "{}"


# ------------------------------------------------------------------
# Vertex: unknown-model cost + extract paths + service-account missing fields
# ------------------------------------------------------------------


def test_vertex_unknown_model_cost_uses_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    # Generate a minimal valid SA file in-memory so the credential check passes.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("utf-8")
    )
    import json

    sa_path = tmp_path / "sa.json"
    sa_path.write_text(
        json.dumps(
            {
                "client_email": "x@y.iam",
                "private_key": pem,
                "private_key_id": "kid",
            }
        )
    )

    def handler(req: httpx.Request) -> httpx.Response:
        if "/token" in str(req.url):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 1000},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = VertexAiProvider(
        project="p",
        credentials_path=str(sa_path),
        model="gemini-future-xyz",
        http_client=client,
        _clock=lambda: 1_700_000_000.0,
    )
    response = provider.complete(LlmRequest(system=""))
    assert response.cost_usd > 0  # default rates kicked in


def test_vertex_sa_missing_fields(tmp_path: Any) -> None:
    import json

    from engine.errors.base import LlmMissingKeyError
    from engine.llm.providers.vertex import _read_service_account

    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps({"client_email": "x"}))  # missing other fields
    with pytest.raises(LlmMissingKeyError):
        _read_service_account(str(bad_path))


def test_vertex_sa_not_object(tmp_path: Any) -> None:
    from engine.errors.base import LlmMissingKeyError
    from engine.llm.providers.vertex import _read_service_account

    bad_path = tmp_path / "list.json"
    bad_path.write_text("[]")
    with pytest.raises(LlmMissingKeyError):
        _read_service_account(str(bad_path))


def test_vertex_extract_no_candidates() -> None:
    p = VertexAiProvider(project="p")
    assert p.extract_response_text({}) == "{}"
    assert p.extract_response_text({"candidates": [{}]}) == "{}"


def test_vertex_oauth_4xx_raises(tmp_path: Any) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("utf-8")
    )
    import json

    sa_path = tmp_path / "sa.json"
    sa_path.write_text(
        json.dumps({"client_email": "x@y.iam", "private_key": pem, "private_key_id": "kid"})
    )

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = VertexAiProvider(
        project="p",
        credentials_path=str(sa_path),
        http_client=client,
        _clock=lambda: 1_700_000_000.0,
    )
    with pytest.raises(LlmRequestRejectedError):
        provider.complete(LlmRequest(system="ping"))


def test_vertex_non_rsa_key_rejected() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from engine.errors.base import LlmMissingKeyError
    from engine.llm.providers.vertex import sign_jwt

    ec_key = ec.generate_private_key(ec.SECP256R1())
    ec_pem = ec_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    with pytest.raises(LlmMissingKeyError):
        sign_jwt(
            private_key_pem=ec_pem,
            client_email="x@y.iam",
            private_key_id="kid",
            issued_at=0,
        )


# ------------------------------------------------------------------
# Redaction: include-prompts policy round-trip
# ------------------------------------------------------------------


def test_redaction_include_prompts_keeps_string_prompt() -> None:
    from engine.llm.redaction import LlmRedactionPolicy, redact_request

    payload = {"prompt": "long prompt text"}
    redacted = redact_request(payload, policy=LlmRedactionPolicy(include_prompts_in_audit=False))
    assert redacted["prompt"]["chars"] == len("long prompt text")
