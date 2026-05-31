"""LLM-specific redaction policy and the request/response summarizers."""

from __future__ import annotations

from engine.llm.redaction import (
    LlmRedactionPolicy,
    redact_auth_headers,
    redact_request,
    redact_response,
)


def test_request_messages_array_collapsed_to_count() -> None:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "secret prompt"},
            {"role": "user", "content": "very secret user message"},
        ],
    }
    redacted = redact_request(payload)
    assert redacted["model"] == "gpt-4o-mini"
    assert redacted["messages"] == {"count": 2, "redacted": True}
    assert "secret" not in str(redacted)


def test_request_system_field_collapsed() -> None:
    payload = {"system": "very long locked prompt"}
    redacted = redact_request(payload)
    assert redacted["system"]["redacted"] is True
    assert redacted["system"]["chars"] == len("very long locked prompt")


def test_request_response_schema_summarized() -> None:
    payload = {"response_schema": {"type": "object", "properties": {"x": {"type": "string"}}}}
    redacted = redact_request(payload)
    assert redacted["response_schema"] == {"structured_output": True}


def test_request_with_include_prompts_true_keeps_messages() -> None:
    payload = {"messages": [{"role": "user", "content": "hi"}]}
    policy = LlmRedactionPolicy(include_prompts_in_audit=True)
    redacted = redact_request(payload, policy=policy)
    # Still passes through redact() which masks role-aware secret keys,
    # but the content survives because the array isn't collapsed.
    assert isinstance(redacted["messages"], list)


def test_response_choices_redacted_by_default() -> None:
    payload = {
        "choices": [{"message": {"content": "model output"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        "model": "gpt-4o-mini",
    }
    redacted = redact_response(payload)
    assert redacted["choices"] == {"redacted": True}
    assert redacted["usage"] == {"prompt_tokens": 10, "completion_tokens": 20}
    assert redacted["model"] == "gpt-4o-mini"


def test_response_candidates_redacted_for_gemini_shape() -> None:
    payload = {
        "candidates": [{"content": {"parts": [{"text": "secret answer"}]}}],
        "usageMetadata": {"promptTokenCount": 10},
    }
    redacted = redact_response(payload)
    assert redacted["candidates"] == {"redacted": True}
    assert redacted["usageMetadata"]["promptTokenCount"] == 10
    assert "secret" not in str(redacted)


def test_response_with_include_text_true_keeps_choices() -> None:
    payload = {"choices": [{"message": {"content": "x"}}]}
    policy = LlmRedactionPolicy(include_response_text_in_audit=True)
    redacted = redact_response(payload, policy=policy)
    assert isinstance(redacted["choices"], list)


def test_redact_auth_headers_masks_bearer() -> None:
    headers = {"Authorization": "Bearer sk-very-secret", "Content-Type": "application/json"}
    redacted = redact_auth_headers(headers)
    assert "sk-very-secret" not in str(redacted)
    assert redacted["Content-Type"] == "application/json"
