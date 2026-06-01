"""Shared stdlib HTTP client for the Phase 25 integrations.

our engineering rules forbids pulling in ``requests`` just to call a REST API;
the Phase 17 PR / MR posters proved the pattern works. Every Phase 25
adapter reuses this client so retry, redaction, and timeout semantics
are identical across BrowserStack, Sauce Labs, Slack, GitHub, GitLab,
Jira, and Linear.

our engineering rules: ``Authorization`` headers, webhook URLs, and tokens are
never logged. URLs go through :func:`redact_url` (query strings are
stripped) and error bodies are clipped to 200 chars before they reach
exceptions or log records.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

DEFAULT_USER_AGENT: Final[str] = "sentinelqa-integrations/1"
DEFAULT_TIMEOUT_S: Final[float] = 30.0
DEFAULT_RETRIES: Final[int] = 3
DEFAULT_BACKOFF_S: Final[float] = 1.0
RETRYABLE_STATUSES: Final[frozenset[int]] = frozenset({429, 502, 503, 504})

logger = logging.getLogger("sentinelqa.integrations.http")


class IntegrationHttpError(RuntimeError):
    """Raised when an integration HTTP call cannot complete safely."""


@dataclass(frozen=True)
class RetrySpec:
    """Retry policy for transient HTTP failures."""

    max_attempts: int = DEFAULT_RETRIES
    base_backoff_s: float = DEFAULT_BACKOFF_S


@dataclass(frozen=True)
class AuthHeader:
    """A non-logged ``(name, value)`` pair the client adds to every request."""

    name: str
    value: str

    @classmethod
    def bearer(cls, token: str) -> AuthHeader:
        return cls(name="Authorization", value=f"Bearer {token}")

    @classmethod
    def basic(cls, username: str, password: str) -> AuthHeader:
        raw = f"{username}:{password}".encode()
        encoded = base64.b64encode(raw).decode("ascii")
        return cls(name="Authorization", value=f"Basic {encoded}")

    @classmethod
    def header(cls, name: str, value: str) -> AuthHeader:
        return cls(name=name, value=value)


class HttpClient:
    """Tiny ``urllib``-based HTTP client used by every Phase 25 adapter.

    The class is intentionally small. Tests subclass it (or its
    ``_request`` hook) to intercept calls without monkeypatching
    ``urllib.request`` globally.
    """

    def __init__(
        self,
        *,
        auth: AuthHeader | None = None,
        retry: RetrySpec | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        user_agent: str = DEFAULT_USER_AGENT,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._auth = auth
        self._retry = retry or RetrySpec()
        self._timeout_s = timeout_s
        self._user_agent = user_agent
        self._extra_headers = dict(extra_headers or {})

    # --- public ----------------------------------------------------------------

    def get_json(self, url: str) -> Any:
        return self._request("GET", url, body=None)

    def post_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        return self._request("POST", url, body=payload)

    def put_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        return self._request("PUT", url, body=payload)

    def patch_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        return self._request("PATCH", url, body=payload)

    def delete_json(self, url: str) -> Any:
        return self._request("DELETE", url, body=None)

    def post_text(self, url: str, payload: Mapping[str, Any]) -> str:
        """POST JSON and return the response body as text (no JSON parse).

        Used by callers whose endpoint returns a non-JSON status string
        (Slack incoming webhooks return ``"ok"``).
        """

        result = self._request("POST", url, body=payload, parse_json=False)
        return result if isinstance(result, str) else ""

    # --- internals -------------------------------------------------------------

    def _headers(self, *, content_type: str | None) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        if self._auth is not None:
            headers[self._auth.name] = self._auth.value
        headers.update(self._extra_headers)
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None,
        parse_json: bool = True,
    ) -> Any:
        encoded: bytes | None = None
        content_type: str | None = None
        if body is not None:
            encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
            content_type = "application/json"

        last_error: Exception | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            request = urllib.request.Request(
                url=url,
                data=encoded,
                method=method,
                headers=self._headers(content_type=content_type),
            )
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                    raw = response.read()
                    if not raw:
                        return "" if not parse_json else {}
                    text = raw.decode("utf-8", errors="replace")
                    if not parse_json:
                        return text
                    return json.loads(text)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in RETRYABLE_STATUSES and attempt < self._retry.max_attempts:
                    sleep_for = self._backoff_seconds(attempt, exc.headers)
                    logger.warning(
                        "integrations.http: %s %s -> %d (attempt %d/%d), " "retrying in %.1fs",
                        method,
                        redact_url(url),
                        exc.code,
                        attempt,
                        self._retry.max_attempts,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                reason = safe_reason(exc)
                raise IntegrationHttpError(
                    f"{method} {redact_url(url)} -> HTTP {exc.code}: {reason}"
                ) from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < self._retry.max_attempts:
                    sleep_for = self._retry.base_backoff_s * (2 ** (attempt - 1))
                    logger.warning(
                        "integrations.http: %s %s -> %s (attempt %d/%d), " "retrying in %.1fs",
                        method,
                        redact_url(url),
                        exc.reason,
                        attempt,
                        self._retry.max_attempts,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                raise IntegrationHttpError(
                    f"{method} {redact_url(url)} failed: {exc.reason}"
                ) from exc

        raise IntegrationHttpError(f"{method} {redact_url(url)} exhausted retries: {last_error!r}")

    def _backoff_seconds(self, attempt: int, headers: Any) -> float:
        sleep_for: float = self._retry.base_backoff_s * (2 ** (attempt - 1))
        if headers is None:
            return sleep_for
        retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
        if retry_after:
            with contextlib.suppress(ValueError):
                sleep_for = max(sleep_for, float(retry_after))
        return sleep_for


def redact_url(url: str) -> str:
    """Drop the query string and the userinfo component from a URL.

    Webhook URLs sometimes carry the secret in the query string (Slack
    incoming webhooks do). Logging the path-only form keeps the host
    + endpoint context for debugging without leaking the secret.
    """

    # Strip userinfo: scheme://user:pw@host/path -> scheme://host/path
    scheme_sep = url.find("://")
    work = url
    if scheme_sep != -1:
        host_start = scheme_sep + 3
        at_index = url.find("@", host_start)
        slash_index = url.find("/", host_start)
        if at_index != -1 and (slash_index == -1 or at_index < slash_index):
            work = url[: scheme_sep + 3] + url[at_index + 1 :]
    sep_index = work.find("?")
    if sep_index == -1:
        return work
    return work[:sep_index] + "?<redacted>"


def safe_reason(exc: urllib.error.HTTPError) -> str:
    """Return a clipped, header-free description of an HTTP error.

    GitHub / GitLab / Atlassian sometimes echo request bodies into
    error responses, so we clip to 200 chars and never include response
    headers (which can carry tracing tokens).
    """

    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    body = body[:200]
    return body or exc.reason or "unknown"


__all__ = [
    "AuthHeader",
    "HttpClient",
    "IntegrationHttpError",
    "RetrySpec",
    "redact_url",
    "safe_reason",
    "DEFAULT_USER_AGENT",
    "DEFAULT_RETRIES",
    "DEFAULT_BACKOFF_S",
    "DEFAULT_TIMEOUT_S",
    "RETRYABLE_STATUSES",
]
