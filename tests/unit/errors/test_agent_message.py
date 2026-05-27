"""Agent-message serialization tests."""

from __future__ import annotations

from engine.errors import ConfigSchemaError, UnknownHostError


def test_agent_message_shape() -> None:
    err = UnknownHostError(host="evil.example.com")
    msg = err.to_agent_message()
    assert msg["type"] == "error"
    assert msg["code"] == "E-SAFE-001"
    assert "host" in msg["context"]
    assert msg["exit_code"] == 4
    assert "suggested_fix" in msg


def test_agent_message_redacts_secrets() -> None:
    err = ConfigSchemaError(
        detail="boom",
        technical_context={"password": "hunter2", "field": "auth.password"},
    )
    msg = err.to_agent_message()
    assert msg["context"]["password"] == "[REDACTED:password]"
    # Non-secret context survives untouched.
    assert msg["context"]["field"] == "auth.password"
