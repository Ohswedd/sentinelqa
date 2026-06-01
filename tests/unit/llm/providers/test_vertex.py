"""VertexAiProvider — JWT signing + OAuth2 exchange + caching.

We generate a fresh RSA private key in-memory per test so the fixture
contains zero secret material. The OAuth endpoint is
mocked via ``httpx.MockTransport``.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from engine.errors.base import LlmMissingKeyError
from engine.llm import LlmRequest
from engine.llm.providers.vertex import VertexAiProvider, sign_jwt


@pytest.fixture
def rsa_keypair() -> tuple[str, rsa.RSAPublicKey]:
    """Generate an RSA-2048 keypair; return (private_pem, public_key)."""

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return pem, private_key.public_key()


@pytest.fixture
def service_account_file(tmp_path: Any, rsa_keypair: tuple[str, Any]) -> str:
    """Write a minimal service-account JSON to disk; return its path."""

    pem, _ = rsa_keypair
    sa = {
        "type": "service_account",
        "project_id": "sentinel-test",
        "private_key_id": "abc123",
        "private_key": pem,
        "client_email": "test-sa@sentinel-test.iam.gserviceaccount.com",
        "client_id": "999",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    path = tmp_path / "sa.json"
    path.write_text(json.dumps(sa))
    return str(path)


def test_sign_jwt_round_trip(rsa_keypair: tuple[str, Any]) -> None:
    pem, public_key = rsa_keypair
    token = sign_jwt(
        private_key_pem=pem,
        client_email="user@example.com",
        private_key_id="kid-1",
        issued_at=1_700_000_000,
        ttl_seconds=3600,
    )
    header_b64, claims_b64, sig_b64 = token.split(".")

    def _b64dec(s: str) -> bytes:
        padding_needed = (-len(s)) % 4
        return base64.urlsafe_b64decode(s + "=" * padding_needed)

    header = json.loads(_b64dec(header_b64))
    claims = json.loads(_b64dec(claims_b64))
    assert header == {"alg": "RS256", "typ": "JWT", "kid": "kid-1"}
    assert claims["iss"] == "user@example.com"
    assert claims["iat"] == 1_700_000_000
    assert claims["exp"] == 1_700_003_600
    assert claims["aud"] == "https://oauth2.googleapis.com/token"

    # Verify the signature against the public key.
    signing_input = (header_b64 + "." + claims_b64).encode("ascii")
    signature = _b64dec(sig_b64)
    public_key.verify(
        signature,
        signing_input,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_vertex_oauth_exchange_caches_token(service_account_file: str) -> None:
    fake_now = [1_700_000_000.0]
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        if "/token" in str(req.url):
            return httpx.Response(
                200,
                json={"access_token": "ya29-test-token", "expires_in": 3600},
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = VertexAiProvider(
        project="sentinel-test",
        region="us-central1",
        credentials_path=service_account_file,
        http_client=client,
        _clock=lambda: fake_now[0],
    )
    # Two calls — token cached after the first.
    provider.complete(LlmRequest(system="ping"))
    provider.complete(LlmRequest(system="ping"))
    token_calls = [r for r in captured if "/token" in str(r.url)]
    assert len(token_calls) == 1, "OAuth token should be cached"

    # Advance past the TTL — second exchange.
    fake_now[0] += 4000
    provider.complete(LlmRequest(system="ping"))
    token_calls = [r for r in captured if "/token" in str(r.url)]
    assert len(token_calls) == 2


def test_vertex_missing_credentials_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    provider = VertexAiProvider(project="p")
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_vertex_credentials_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/does/not/exist.json")
    provider = VertexAiProvider(project="p")
    with pytest.raises(LlmMissingKeyError):
        provider.complete(LlmRequest(system="ping"))


def test_vertex_doctor_available_with_valid_credentials(
    service_account_file: str,
) -> None:
    provider = VertexAiProvider(
        project="sentinel-test",
        credentials_path=service_account_file,
        _clock=lambda: 1_700_000_000.0,
    )
    health = provider.doctor()
    assert health.status == "available"
    assert "sentinel-test" in health.detail


def test_vertex_doctor_unavailable_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    health = VertexAiProvider(project="p").doctor()
    assert health.status == "unavailable"
