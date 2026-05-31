"""Google Vertex AI provider (Phase 30 task 30.05, ADR-0042).

Calls Vertex AI's REST endpoint at
``https://<region>-aiplatform.googleapis.com/v1/projects/<project>/
locations/<region>/publishers/google/models/<model>:generateContent``
via ``httpx``. No ``google-cloud-aiplatform`` or ``google-auth`` SDKs
are imported.

Auth: Google service-account JSON key file referenced by
``GOOGLE_APPLICATION_CREDENTIALS``. The adapter signs a JWT (RS256
against the service-account private key) and exchanges it for an OAuth2
access token via ``https://oauth2.googleapis.com/token``; tokens are
cached for their TTL minus a 60s safety margin.

RS256 signing uses the PyCA :mod:`cryptography` library — see
``engine/pyproject.toml`` for the dependency justification.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from engine.errors.base import LlmMissingKeyError, LlmRequestRejectedError
from engine.llm.budget import estimate_cost_usd
from engine.llm.protocol import LlmRequest, ProviderHealth
from engine.llm.providers._http_base import HttpLlmProviderBase

# Vertex pricing differs from Google AI Studio (`Gemini`). These are the
# canonical Vertex defaults (per million tokens converted to per-1k).
_PRICING_USD_PER_1K: dict[str, tuple[float, float]] = {
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-2.0-flash": (0.0001, 0.0004),
}

_OAUTH_TOKEN_URL: str = "https://oauth2.googleapis.com/token"
_SCOPE: str = "https://www.googleapis.com/auth/cloud-platform"
_TOKEN_TTL_SECONDS: int = 3600
_REFRESH_SAFETY_MARGIN: int = 60


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _read_service_account(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data: Any = json.load(fh)
    if not isinstance(data, dict):
        raise LlmMissingKeyError(
            provider="vertex",
            env_var=f"GOOGLE_APPLICATION_CREDENTIALS={path} (file is not a JSON object)",
        )
    required = {"client_email", "private_key", "private_key_id"}
    missing = required - set(data)
    if missing:
        raise LlmMissingKeyError(
            provider="vertex",
            env_var=f"GOOGLE_APPLICATION_CREDENTIALS={path} (missing fields: {sorted(missing)!r})",
        )
    return data


def sign_jwt(
    *,
    private_key_pem: str,
    client_email: str,
    private_key_id: str,
    scope: str = _SCOPE,
    audience: str = _OAUTH_TOKEN_URL,
    issued_at: int,
    ttl_seconds: int = _TOKEN_TTL_SECONDS,
) -> str:
    """Build and sign an RS256 JWT bearer assertion.

    Spec: RFC 7515 (JWS), RFC 7519 (JWT). Used by Google's
    ``urn:ietf:params:oauth:grant-type:jwt-bearer`` exchange.
    """

    header = {"alg": "RS256", "typ": "JWT", "kid": private_key_id}
    claims = {
        "iss": client_email,
        "scope": scope,
        "aud": audience,
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(claims, separators=(",", ":")).encode())
    ).encode("ascii")

    key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    if not isinstance(key, rsa.RSAPrivateKey):
        raise LlmMissingKeyError(
            provider="vertex",
            env_var="GOOGLE_APPLICATION_CREDENTIALS (private_key must be RSA)",
        )
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return signing_input.decode("ascii") + "." + _b64url(signature)


@dataclass
class VertexAiProvider(HttpLlmProviderBase):
    name: ClassVar[str] = "vertex"
    version: ClassVar[str] = "1.0.0"
    DEFAULT_MODEL: ClassVar[str] = "gemini-1.5-flash"
    API_KEY_ENV: ClassVar[str] = "GOOGLE_APPLICATION_CREDENTIALS"

    project: str = ""
    region: str = "us-central1"
    credentials_path: str | None = None  # if None, reads env at call time
    _token: str = ""
    _token_expires_at: float = 0.0
    _service_account: dict[str, Any] = field(default_factory=dict)
    _clock: Any = field(default_factory=lambda: time.time)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _credentials_path(self) -> str:
        path = self.credentials_path or os.environ.get(self.API_KEY_ENV, "")
        if not path:
            raise LlmMissingKeyError(provider=self.name, env_var=self.API_KEY_ENV)
        if not os.path.exists(path):
            raise LlmMissingKeyError(
                provider=self.name,
                env_var=f"{self.API_KEY_ENV}={path} (file not found)",
            )
        return path

    def _resolve_api_key(self) -> str:
        # Vertex's "key" is an access token, fetched via JWT exchange.
        return self._access_token()

    def _service_account_dict(self) -> dict[str, Any]:
        if not self._service_account:
            path = self._credentials_path()
            self._service_account = _read_service_account(path)
        return self._service_account

    def _access_token(self) -> str:
        now = float(self._clock())
        if self._token and now < self._token_expires_at - _REFRESH_SAFETY_MARGIN:
            return self._token

        sa = self._service_account_dict()
        jwt_str = sign_jwt(
            private_key_pem=sa["private_key"],
            client_email=sa["client_email"],
            private_key_id=sa["private_key_id"],
            issued_at=int(now),
            ttl_seconds=_TOKEN_TTL_SECONDS,
        )

        client = self.http_client or httpx.Client(timeout=self.request_timeout_seconds)
        owns = self.http_client is None
        try:
            response = client.post(
                _OAUTH_TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt_str,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        finally:
            if owns:
                client.close()
        if response.status_code >= 400:
            raise LlmRequestRejectedError(
                provider=self.name,
                status_code=response.status_code,
                detail=response.text[:200],
            )
        body = response.json()
        self._token = body.get("access_token", "")
        expires_in = int(body.get("expires_in", _TOKEN_TTL_SECONDS))
        self._token_expires_at = now + expires_in
        return self._token

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def endpoint_url(self) -> str:
        model = self.model or self.DEFAULT_MODEL
        return (
            f"https://{self.region}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project}/locations/{self.region}/publishers/google/models/"
            f"{model}:generateContent"
        )

    def auth_headers(self, *, api_key: str) -> dict[str, str]:
        # Vertex uses an OAuth2 access token (not the raw JWT).
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(self, *, request: LlmRequest, model: str) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "ping"}]}]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
        }
        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.response_schema is not None:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = request.response_schema
        return payload

    def extract_response_text(self, body: dict[str, Any]) -> str:
        candidates = body.get("candidates") or []
        for cand in candidates:
            content = cand.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                text = part.get("text")
                if isinstance(text, str):
                    return text
        return "{}"

    def usage_from_response(self, body: dict[str, Any]) -> tuple[int, int]:
        usage = body.get("usageMetadata") or {}
        return int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0))

    def cost_from_response(
        self,
        *,
        body: dict[str, Any],
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        rates = _PRICING_USD_PER_1K.get(model)
        if rates is None:
            return estimate_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        in_rate, out_rate = rates
        return estimate_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            price_per_1k_input=in_rate,
            price_per_1k_output=out_rate,
        )

    def doctor(self) -> ProviderHealth:
        """Decode credentials, verify JWT signing works, report project + region.

        Does NOT make a network call by default — the credential fetch
        proves we can authenticate without burning Vertex quota.
        """

        model = self.model or self.DEFAULT_MODEL
        try:
            sa = self._service_account_dict()
        except LlmMissingKeyError as exc:
            return ProviderHealth(
                provider=self.name,
                model=model,
                status="unavailable",
                latency_ms=0.0,
                detail=exc.message,
            )
        try:
            sign_jwt(
                private_key_pem=sa["private_key"],
                client_email=sa["client_email"],
                private_key_id=sa["private_key_id"],
                issued_at=int(float(self._clock())),
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.name,
                model=model,
                status="unavailable",
                latency_ms=0.0,
                detail=f"JWT signing failed: {type(exc).__name__}",
            )
        return ProviderHealth(
            provider=self.name,
            model=model,
            status="available",
            latency_ms=0.0,
            detail=(
                f"project={self.project or sa.get('project_id', 'unknown')!r}, "
                f"region={self.region!r}"
            ),
        )


PRICING_USD_PER_1K = _PRICING_USD_PER_1K


__all__ = ["VertexAiProvider", "PRICING_USD_PER_1K", "sign_jwt"]
