"""Unit tests for ``integrations._http`` (Phase 25 shared helpers)."""

from __future__ import annotations

import io
import urllib.error
from collections.abc import Mapping
from typing import Any

import pytest
from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
    redact_url,
    safe_reason,
)

# ---------------------------------------------------------------------------
# AuthHeader
# ---------------------------------------------------------------------------


def test_bearer_factory_produces_authorization_header() -> None:
    h = AuthHeader.bearer("tok")
    assert h.name == "Authorization"
    assert h.value == "Bearer tok"


def test_basic_factory_base64_encodes_user_password() -> None:
    h = AuthHeader.basic("alice", "p4ss")
    assert h.name == "Authorization"
    # base64("alice:p4ss") == "YWxpY2U6cDRzcw=="
    assert h.value == "Basic YWxpY2U6cDRzcw=="


def test_header_factory_passes_arbitrary_pair() -> None:
    h = AuthHeader.header("PRIVATE-TOKEN", "abc")
    assert h.name == "PRIVATE-TOKEN"
    assert h.value == "abc"


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/p", "https://example.com/p"),
        ("https://example.com/p?secret=1", "https://example.com/p?<redacted>"),
        ("https://user:pw@example.com/p", "https://example.com/p"),
        (
            "https://user:pw@example.com/p?t=1",
            "https://example.com/p?<redacted>",
        ),
        # query string before any path
        ("https://example.com?token=x", "https://example.com?<redacted>"),
    ],
)
def test_redact_url(url: str, expected: str) -> None:
    assert redact_url(url) == expected


def test_safe_reason_clips_body_and_returns_text() -> None:
    body = b"x" * 1000
    exc = urllib.error.HTTPError("http://x", 500, "Server Error", {}, io.BytesIO(body))
    reason = safe_reason(exc)
    assert len(reason) == 200
    assert reason == "x" * 200


def test_safe_reason_falls_back_to_exc_reason() -> None:
    exc = urllib.error.HTTPError("http://x", 500, "Server Error", {}, io.BytesIO(b""))
    assert safe_reason(exc) == "Server Error"


# ---------------------------------------------------------------------------
# HttpClient header construction
# ---------------------------------------------------------------------------


class _Recorder(HttpClient):
    """HttpClient subclass that returns its computed headers + body."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.captured: list[tuple[str, dict[str, str]]] = []

    def headers_for(self, *, content_type: str | None = None) -> dict[str, str]:
        return self._headers(content_type=content_type)


def test_http_client_headers_include_user_agent_and_accept() -> None:
    client = _Recorder()
    headers = client.headers_for()
    assert headers["User-Agent"].startswith("sentinelqa-integrations/")
    assert headers["Accept"] == "application/json"


def test_http_client_headers_include_auth_when_set() -> None:
    client = _Recorder(auth=AuthHeader.bearer("tok"))
    headers = client.headers_for()
    assert headers["Authorization"] == "Bearer tok"


def test_http_client_headers_skip_auth_when_unset() -> None:
    client = _Recorder()
    headers = client.headers_for()
    assert "Authorization" not in headers


def test_http_client_headers_add_content_type_when_body_present() -> None:
    client = _Recorder()
    headers = client.headers_for(content_type="application/json")
    assert headers["Content-Type"] == "application/json"


def test_http_client_extra_headers_override_defaults() -> None:
    client = _Recorder(extra_headers={"X-GitHub-Api-Version": "2022-11-28"})
    headers = client.headers_for()
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


# ---------------------------------------------------------------------------
# HttpClient retry behaviour
# ---------------------------------------------------------------------------


def test_retryable_status_triggers_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _Response:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    def _urlopen(request: Any, timeout: float) -> Any:
        del timeout
        calls.append(request.full_url)
        if len(calls) < 3:
            raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, io.BytesIO(b""))
        return _Response(b'{"ok": true}')

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", _urlopen)
    monkeypatch.setattr("integrations._http.time.sleep", lambda _: None)

    client = HttpClient(retry=RetrySpec(max_attempts=3, base_backoff_s=0.0))
    result = client.get_json("https://example.com/api")
    assert result == {"ok": True}
    assert len(calls) == 3


def test_non_retryable_status_raises_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _urlopen(request: Any, timeout: float) -> Any:
        del timeout
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 400, "Bad", {}, io.BytesIO(b"nope"))

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", _urlopen)
    monkeypatch.setattr("integrations._http.time.sleep", lambda _: None)

    client = HttpClient(retry=RetrySpec(max_attempts=5, base_backoff_s=0.0))
    with pytest.raises(IntegrationHttpError) as exc:
        client.get_json("https://example.com/api")
    assert "HTTP 400" in str(exc.value)
    # 400 is non-retryable, so exactly one call.
    assert len(calls) == 1


def test_url_error_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _urlopen(request: Any, timeout: float) -> Any:
        del timeout
        calls.append(request.full_url)
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", _urlopen)
    monkeypatch.setattr("integrations._http.time.sleep", lambda _: None)

    client = HttpClient(retry=RetrySpec(max_attempts=3, base_backoff_s=0.0))
    with pytest.raises(IntegrationHttpError):
        client.get_json("https://example.com/api")
    assert len(calls) == 3


def test_retry_after_header_floors_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def _urlopen(request: Any, timeout: float) -> Any:
        del timeout
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many",
                {"Retry-After": "7"},  # type: ignore[arg-type]
                io.BytesIO(b""),
            )

        class _R:
            def __enter__(self) -> _R:
                return self

            def __exit__(self, *args: Any) -> None:
                return None

            def read(self) -> bytes:
                return b'{"ok":true}'

        return _R()

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", _urlopen)
    monkeypatch.setattr("integrations._http.time.sleep", sleeps.append)
    client = HttpClient(retry=RetrySpec(max_attempts=2, base_backoff_s=0.5))
    result = client.get_json("https://example.com/api")
    assert result == {"ok": True}
    assert sleeps == [7.0]


def test_post_text_returns_plain_string(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        def __enter__(self) -> _R:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    def _urlopen(request: Any, timeout: float) -> Any:
        del timeout, request
        return _R()

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", _urlopen)
    client = HttpClient()
    body = client.post_text("https://example.com/h", {"x": 1})
    assert body == "ok"


def test_empty_response_returns_empty_string_for_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _R:
        def __enter__(self) -> _R:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b""

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", lambda req, timeout: _R())
    client = HttpClient()
    assert client.post_text("https://example/x", {"a": 1}) == ""


def test_empty_response_returns_empty_dict_for_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _R:
        def __enter__(self) -> _R:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b""

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", lambda req, timeout: _R())
    client = HttpClient()
    assert client.get_json("https://example/x") == {}


def test_request_serializes_json_body_with_compact_separators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _R:
        def __enter__(self) -> _R:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok":true}'

    def _urlopen(request: Any, timeout: float) -> Any:
        del timeout
        captured["data"] = request.data
        captured["headers"] = dict(request.header_items())
        return _R()

    monkeypatch.setattr("integrations._http.urllib.request.urlopen", _urlopen)
    client = HttpClient()
    client.post_json("https://x.test", {"b": 2, "a": 1})
    assert captured["data"] == b'{"b":2,"a":1}'
    # urllib normalizes header names; Content-type/Content-Type both valid.
    headers_norm: Mapping[str, str] = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers_norm["content-type"] == "application/json"
