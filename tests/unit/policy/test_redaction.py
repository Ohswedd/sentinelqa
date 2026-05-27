"""Redaction unit tests — CLAUDE.md §33 coverage."""

from __future__ import annotations

import json

import pytest
from engine.policy.redaction import (
    add_allowlist_token,
    clear_allowlist,
    redact,
    redact_headers,
    redact_url,
)


@pytest.fixture(autouse=True)
def _reset_allowlist() -> None:
    clear_allowlist()


def test_password_key_redacted() -> None:
    out = redact({"password": "hunter2", "ok": "yes"})
    assert out == {"password": "[REDACTED:password]", "ok": "yes"}


def test_cookie_header() -> None:
    out = redact({"set-cookie": "session=abc"})
    assert out["set-cookie"].startswith("[REDACTED:cookie")


def test_bearer_token_in_string() -> None:
    out = redact("Authorization: Bearer abcdef0123456789")
    assert "Bearer abcdef0123456789" not in out
    assert "[REDACTED:bearer_token]" in out


def test_jwt_redacted() -> None:
    jwt = "eyJhbGciOi.eyJzdWIiOi.signaturepart"
    out = redact({"token": jwt, "msg": jwt})
    # Token key is redacted by key name.
    assert out["token"].startswith("[REDACTED:")
    # Value-level pass also catches it when it appears in a non-secret key.
    assert "[REDACTED:jwt]" in out["msg"]


def test_aws_access_key_in_log_line() -> None:
    line = "found AKIAIOSFODNN7EXAMPLE in the env"
    out = redact(line)
    assert "AKIAIOSFODNN7EXAMPLE" not in out


def test_pem_private_key_redacted() -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj\n-----END RSA PRIVATE KEY-----"
    out = redact(pem)
    assert "RSA PRIVATE KEY" not in out
    assert "[REDACTED:private_key]" in out


def test_anthropic_or_openai_key_redacted() -> None:
    key = "sk-abc123def456ghi789jkl012mno345"
    out = redact(key)
    assert out == "[REDACTED:openai_or_anthropic_key]"


def test_high_entropy_token_redacted() -> None:
    # A purely random-looking 40-character token.
    tok = "Z9p7Lk2QmRtVxN8wJ4hG6sA1bC3dE5fHiOoXyZqK"
    out = redact(tok)
    assert "[REDACTED:high_entropy_token]" in out


def test_low_entropy_text_passes_through() -> None:
    text = "the quick brown fox jumps over the lazy dog"
    assert redact(text) == text


def test_allowlist_disables_value_match() -> None:
    tok = "Z9p7Lk2QmRtVxN8wJ4hG6sA1bC3dE5fHiOoXyZqK"
    add_allowlist_token(tok)
    assert tok in redact(tok)


def test_depth_limit() -> None:
    deep: dict = {}
    cur = deep
    for _ in range(10):
        cur["next"] = {}
        cur = cur["next"]
    out = redact(deep, depth=3)
    # The deepest field is replaced with the depth-limit marker.
    assert json.dumps(out) != json.dumps(deep)


def test_redact_headers_case_insensitive() -> None:
    out = redact_headers({"Authorization": "Bearer abc", "X-API-Key": "k", "Accept": "json"})
    assert out["Authorization"].startswith("[REDACTED:")
    assert out["X-API-Key"].startswith("[REDACTED:")
    assert out["Accept"] == "json"


def test_redact_url_strips_userinfo_and_secret_query() -> None:
    redacted = redact_url("https://alice:hunter2@api.x/path?token=secret&q=hi")
    assert "alice:hunter2" not in redacted
    assert "[REDACTED:userinfo]" in redacted
    assert "[REDACTED:url_token]" in redacted
    assert "q=hi" in redacted


def test_redact_preserves_non_string_scalars() -> None:
    out = redact({"count": 5, "ok": True, "ratio": 0.5})
    assert out == {"count": 5, "ok": True, "ratio": 0.5}


def test_session_id_key_redacted() -> None:
    out = redact({"sessionid": "abc123"})
    assert out["sessionid"] == "[REDACTED:session_id]"


def test_authorization_basic_redacted() -> None:
    line = "Authorization: Basic dXNlcjpwYXNz"
    assert "[REDACTED:basic_auth]" in redact(line)


def test_redact_dict_inside_list() -> None:
    out = redact([{"password": "x"}, {"ok": "y"}])
    assert out[0]["password"] == "[REDACTED:password]"
    assert out[1]["ok"] == "y"


def test_redact_empty_password_left_alone() -> None:
    # Empty value isn't a secret — don't flood logs with markers.
    out = redact({"password": ""})
    assert out == {"password": ""}


def test_redact_none_password_passes_through() -> None:
    out = redact({"password": None})
    assert out == {"password": None}
